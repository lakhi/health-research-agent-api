"""Cross-encoder reranking for the knowledge bases, via Cohere Rerank hosted on Azure.

Why a custom Reranker instead of agno's ``CohereReranker``: agno's version constructs a
``cohere.Client``, which talks to api.cohere.com — a US processor, outside the boundary
the gpt-4.1 deployments were cleared for. ``Cohere-rerank-v4.0-fast`` is available in
Sweden Central on the DataZoneStandard SKU (same EU data zone as those deployments) and
is billed through Azure rather than a separate Cohere contract. Calling it directly over
httpx keeps the data in that boundary and adds no new dependency.

Why not an in-process cross-encoder (agno's ``SentenceTransformerReranker``): the SSC
container is 0.5 vCPU / 1 GiB, and an XLM-RoBERTa-large-class reranker such as the
default ``BAAI/bge-reranker-v2-m3`` needs roughly 2 GB for weights alone — it cannot
load there at all, never mind score 50 chunks inside a request.

Blocking I/O is safe here: ``PgVector.async_search`` runs the whole sync search through
``asyncio.to_thread``, so the event loop is never on the call stack when ``rerank`` runs.

Env vars are read with ``os.getenv`` rather than through ``api.settings`` because
``api.settings`` imports ``api.project_configs``, which imports this package — going via
settings would close an import cycle. This matches ``get_azure_embedder()`` next door.
"""

import logging
import os
from typing import Any

import httpx
from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker

logger = logging.getLogger(__name__)

# agno's own default for Knowledge.max_results — how many chunks reach the model when
# nothing reranks them.
DEFAULT_MAX_RESULTS = 10

# Candidate pool to retrieve when a reranker IS configured. agno applies the reranker
# after `stmt.limit(limit)` in PgVector.vector_search, so without over-fetching a
# reranker would only reorder the same 10 chunks the model already sees — it could never
# surface one that vector search ranked 11th. Over-fetching is the only way it earns its
# keep.
RERANK_CANDIDATE_POOL = 50

# Chunks kept after reranking, i.e. how many actually reach the model context. Below
# DEFAULT_MAX_RESULTS on purpose: a reranked 8 beats an unranked 10 and costs fewer
# prompt tokens.
RERANK_TOP_N = 8

DEFAULT_RERANK_MODEL = "Cohere-rerank-v4.0-fast"

# Cohere bills one "search" as a query plus up to 100 documents. Sending more would
# silently cost a second search, so the pool is capped here rather than at the caller.
MAX_DOCUMENTS_PER_SEARCH = 100


class AzureCohereReranker(Reranker):
    """Rerank retrieved chunks with a Cohere Rerank model deployed on Azure.

    Never raises. Any failure — network, auth, malformed response — is logged and
    degrades to the retrieval order, because a reranker outage must not take chat down.
    """

    endpoint: str
    api_key: str
    model: str = DEFAULT_RERANK_MODEL
    top_n: int = RERANK_TOP_N
    timeout_seconds: float = 10.0
    max_documents: int = MAX_DOCUMENTS_PER_SEARCH
    # Injectable so tests can drive an httpx.MockTransport instead of the network.
    http_client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self.http_client is None:
            self.http_client = httpx.Client(timeout=self.timeout_seconds)
        return self.http_client

    def _headers(self) -> dict[str, str]:
        # Both auth schemes are sent deliberately. A Cohere rerank model can be reached
        # either through the Cognitive Services account that already hosts gpt-4.1
        # (which expects `api-key`) or through the Foundry model-inference path (which
        # expects a bearer token), and which one applies is not knowable until the
        # deployment exists. Both go to the one endpoint we configured, over TLS.
        # Trim to whichever the live deployment accepts once that is confirmed.
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "api-key": self.api_key,
        }

    def _request_scores(self, query: str, pool: list[Document]) -> list[tuple[int, float]]:
        """POST one rerank request and return (pool index, relevance score) pairs."""
        payload: dict[str, Any] = {
            "model": self.model,
            "query": query,
            "documents": [doc.content or "" for doc in pool],
            "top_n": min(self.top_n, len(pool)),
        }

        response = self.client.post(self.endpoint, json=payload, headers=self._headers())
        response.raise_for_status()

        scores: list[tuple[int, float]] = []
        for item in response.json().get("results") or []:
            index = item.get("index")
            # An index outside the pool would silently rerank the wrong chunk, so drop it.
            if not isinstance(index, int) or not 0 <= index < len(pool):
                logger.warning("Rerank returned out-of-range index %r for a pool of %d", index, len(pool))
                continue
            raw_score = item.get("relevance_score")
            scores.append((index, float(raw_score) if raw_score is not None else 0.0))

        return scores

    def rerank(self, query: str, documents: list[Document]) -> list[Document]:
        if not documents:
            return []

        pool = documents[: self.max_documents]

        try:
            scores = self._request_scores(query, pool)
        except Exception:
            logger.exception("Azure rerank call failed; falling back to retrieval order")
            return documents[: self.top_n]

        if not scores:
            logger.warning("Azure rerank returned no usable results; falling back to retrieval order")
            return documents[: self.top_n]

        ranked: list[Document] = []
        for index, score in scores:
            doc = pool[index]
            doc.reranking_score = score
            ranked.append(doc)

        ranked.sort(key=lambda d: d.reranking_score if d.reranking_score is not None else float("-inf"), reverse=True)
        return ranked[: self.top_n]


def get_azure_reranker() -> AzureCohereReranker | None:
    """Build the reranker, or return None when it is not configured.

    Returning None leaves ``PgVector(reranker=None)``, which is agno's own default — so
    an unconfigured deployment behaves exactly as it does today. That makes the endpoint
    and key the on/off switch; no separate feature flag to keep in sync.
    """
    endpoint = os.getenv("AZURE_RERANKER_ENDPOINT")
    api_key = os.getenv("AZURE_RERANKER_API_KEY")

    if not endpoint or not api_key:
        # Half-configured is a deployment mistake worth naming, since the symptom
        # otherwise is silently unreranked results.
        if endpoint or api_key:
            logger.warning(
                "Reranking disabled: AZURE_RERANKER_ENDPOINT and AZURE_RERANKER_API_KEY must both be set (only one is)."
            )
        return None

    return AzureCohereReranker(
        endpoint=endpoint,
        api_key=api_key,
        model=os.getenv("AZURE_RERANKER_MODEL") or DEFAULT_RERANK_MODEL,
    )


def get_search_max_results(reranker: Reranker | None) -> int:
    """How many chunks to retrieve, given whether a reranker will cut them back down.

    Must stay tied to the reranker: over-fetching RERANK_CANDIDATE_POOL with nothing to
    trim it would put 50 raw chunks straight into the model context.
    """
    return RERANK_CANDIDATE_POOL if reranker is not None else DEFAULT_MAX_RESULTS
