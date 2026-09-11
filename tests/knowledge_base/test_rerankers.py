"""
Unit tests for the Azure-hosted Cohere reranker.

Covers the request it sends, the ordering it produces, its graceful degradation on every
failure mode, and the coupling between "is a reranker configured" and "how many chunks
do we retrieve". No network: an httpx.MockTransport stands in for the Azure endpoint.
Run with: pytest tests/knowledge_base/test_rerankers.py -v
"""

import json
from collections.abc import Callable

import httpx
import pytest

from agno.knowledge.document import Document

from knowledge_base.rerankers import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_RERANK_MODEL,
    RERANK_CANDIDATE_POOL,
    AzureCohereReranker,
    get_azure_reranker,
    get_search_max_results,
)

ENDPOINT = "https://az-openai-healthsociety.openai.azure.com/openai/deployments/rerank/v2/rerank"

Handler = Callable[[httpx.Request], httpx.Response]


def _docs(n: int) -> list[Document]:
    """n documents whose content states their retrieval position."""
    return [Document(id=str(i), name=f"doc-{i}", content=f"chunk {i}") for i in range(n)]


def _reranker(handler: Handler, **kwargs) -> AzureCohereReranker:
    """A reranker whose HTTP calls are served by `handler` instead of the network."""
    return AzureCohereReranker(
        endpoint=ENDPOINT,
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        **kwargs,
    )


def _always(response: httpx.Response) -> Handler:
    """A handler that answers every request with `response`."""

    def handler(_: httpx.Request) -> httpx.Response:
        return response

    return handler


def _results_response(*pairs: tuple[int, float]) -> httpx.Response:
    """An Azure/Cohere rerank response scoring the given (index, relevance) pairs."""
    return httpx.Response(200, json={"results": [{"index": i, "relevance_score": s} for i, s in pairs]})


def _scoring(*pairs: tuple[int, float], **kwargs) -> AzureCohereReranker:
    """A reranker whose endpoint scores the given (index, relevance) pairs."""
    return _reranker(_always(_results_response(*pairs)), **kwargs)


class TestRequestShape:
    """What we actually send to Azure."""

    def test_sends_model_query_documents_and_top_n(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return _results_response((0, 0.9))

        _reranker(handler, top_n=3).rerank("aufnahmeverfahren", _docs(5))

        assert captured["url"] == ENDPOINT
        assert captured["body"]["model"] == DEFAULT_RERANK_MODEL
        assert captured["body"]["query"] == "aufnahmeverfahren"
        assert captured["body"]["documents"] == ["chunk 0", "chunk 1", "chunk 2", "chunk 3", "chunk 4"]
        assert captured["body"]["top_n"] == 3

    def test_top_n_never_exceeds_the_pool(self):
        """Asking for more documents than were sent is a 400 on some deployments."""
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _results_response((0, 0.9))

        _reranker(handler, top_n=8).rerank("q", _docs(2))

        assert captured["body"]["top_n"] == 2

    def test_sends_both_auth_schemes(self):
        """Deliberate: the account path wants api-key, the inference path wants Bearer."""
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = request.headers
            return _results_response((0, 0.9))

        _reranker(handler).rerank("q", _docs(1))

        assert captured["headers"]["authorization"] == "Bearer test-key"
        assert captured["headers"]["api-key"] == "test-key"

    def test_caps_pool_at_one_billed_search(self):
        """Cohere bills a query + up to 100 documents as one search; more would cost two."""
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _results_response((0, 0.9))

        _reranker(handler).rerank("q", _docs(150))

        assert len(captured["body"]["documents"]) == 100

    def test_none_content_is_sent_as_empty_string(self):
        """Document.content is typed str, but PgVector fills it from a nullable column."""
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _results_response((0, 0.9))

        _reranker(handler).rerank("q", [Document(id="1", name="d", content=None)])  # type: ignore[arg-type]

        assert captured["body"]["documents"] == [""]


class TestOrdering:
    """The reranked result set."""

    def test_reorders_by_relevance_not_retrieval_position(self):
        out = _scoring((2, 0.95), (0, 0.40), (1, 0.10), top_n=3).rerank("q", _docs(3))

        assert [d.content for d in out] == ["chunk 2", "chunk 0", "chunk 1"]

    def test_sorts_even_when_the_api_returns_unsorted_scores(self):
        out = _scoring((0, 0.10), (1, 0.90), (2, 0.50), top_n=3).rerank("q", _docs(3))

        assert [d.content for d in out] == ["chunk 1", "chunk 2", "chunk 0"]

    def test_attaches_the_relevance_score_to_each_document(self):
        out = _scoring((1, 0.77)).rerank("q", _docs(3))

        assert out[0].reranking_score == pytest.approx(0.77)

    def test_truncates_to_top_n(self):
        out = _scoring((0, 0.9), (1, 0.8), (2, 0.7), (3, 0.6), top_n=2).rerank("q", _docs(4))

        assert len(out) == 2

    def test_empty_input_returns_empty_without_calling_the_api(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("should not call the API for an empty document list")

        assert _reranker(handler).rerank("q", []) == []


class TestGracefulDegradation:
    """A reranker outage must not take chat down — and must not flood the prompt."""

    def test_http_error_falls_back_to_retrieval_order_truncated_to_top_n(self):
        reranker = _reranker(_always(httpx.Response(503, text="upstream unavailable")), top_n=3)
        out = reranker.rerank("q", _docs(RERANK_CANDIDATE_POOL))

        assert [d.content for d in out] == ["chunk 0", "chunk 1", "chunk 2"]

    def test_auth_error_falls_back(self):
        reranker = _reranker(_always(httpx.Response(401, json={"error": "unauthorized"})), top_n=2)
        out = reranker.rerank("q", _docs(10))

        assert [d.content for d in out] == ["chunk 0", "chunk 1"]

    def test_transport_error_falls_back(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        out = _reranker(handler, top_n=2).rerank("q", _docs(10))

        assert [d.content for d in out] == ["chunk 0", "chunk 1"]

    def test_malformed_json_falls_back(self):
        out = _reranker(_always(httpx.Response(200, text="not json")), top_n=2).rerank("q", _docs(10))

        assert [d.content for d in out] == ["chunk 0", "chunk 1"]

    def test_empty_results_falls_back(self):
        out = _reranker(_always(httpx.Response(200, json={"results": []})), top_n=2).rerank("q", _docs(10))

        assert [d.content for d in out] == ["chunk 0", "chunk 1"]

    def test_fallback_never_returns_more_than_top_n(self):
        """The point of deviating from agno: an over-fetched pool must not reach the model."""
        out = _reranker(_always(httpx.Response(500)), top_n=8).rerank("q", _docs(RERANK_CANDIDATE_POOL))

        assert len(out) == 8

    def test_out_of_range_index_is_skipped_not_misattributed(self):
        """A bad index would otherwise silently score the wrong chunk."""
        out = _scoring((99, 0.99), (1, 0.50), top_n=3).rerank("q", _docs(3))

        assert [d.content for d in out] == ["chunk 1"]

    def test_non_integer_index_is_skipped(self):
        body = {"results": [{"index": "one", "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5}]}
        out = _reranker(_always(httpx.Response(200, json=body)), top_n=3).rerank("q", _docs(2))

        assert [d.content for d in out] == ["chunk 0"]

    def test_missing_relevance_score_defaults_to_zero(self):
        out = _reranker(_always(httpx.Response(200, json={"results": [{"index": 0}]}))).rerank("q", _docs(1))

        assert out[0].reranking_score == 0.0


class TestFactory:
    """Configuration is the on/off switch — there is no separate feature flag."""

    def test_returns_none_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("AZURE_RERANKER_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_RERANKER_API_KEY", raising=False)

        assert get_azure_reranker() is None

    def test_returns_none_and_warns_when_half_configured(self, monkeypatch, caplog):
        monkeypatch.setenv("AZURE_RERANKER_ENDPOINT", ENDPOINT)
        monkeypatch.delenv("AZURE_RERANKER_API_KEY", raising=False)

        assert get_azure_reranker() is None
        assert "must both be set" in caplog.text

    def test_builds_reranker_when_configured(self, monkeypatch):
        monkeypatch.setenv("AZURE_RERANKER_ENDPOINT", ENDPOINT)
        monkeypatch.setenv("AZURE_RERANKER_API_KEY", "k")
        monkeypatch.delenv("AZURE_RERANKER_MODEL", raising=False)

        reranker = get_azure_reranker()

        assert reranker is not None
        assert reranker.endpoint == ENDPOINT
        assert reranker.model == DEFAULT_RERANK_MODEL

    def test_model_is_overridable(self, monkeypatch):
        monkeypatch.setenv("AZURE_RERANKER_ENDPOINT", ENDPOINT)
        monkeypatch.setenv("AZURE_RERANKER_API_KEY", "k")
        monkeypatch.setenv("AZURE_RERANKER_MODEL", "Cohere-rerank-v4.0-pro")

        reranker = get_azure_reranker()

        assert reranker is not None
        assert reranker.model == "Cohere-rerank-v4.0-pro"


class TestMaxResultsCoupling:
    """Over-fetching without a reranker would put 50 raw chunks in the prompt."""

    def test_over_fetches_when_a_reranker_is_present(self, monkeypatch):
        monkeypatch.setenv("AZURE_RERANKER_ENDPOINT", ENDPOINT)
        monkeypatch.setenv("AZURE_RERANKER_API_KEY", "k")

        assert get_search_max_results(get_azure_reranker()) == RERANK_CANDIDATE_POOL

    def test_keeps_agno_default_without_a_reranker(self):
        assert get_search_max_results(None) == DEFAULT_MAX_RESULTS

    def test_agno_default_is_still_ten(self):
        """Guards the assumption the whole over-fetch design rests on.

        Imported from the `agno.knowledge.knowledge` submodule rather than the
        `agno.knowledge` package: test_hex_gig_knowledge_base.py installs permanent
        sys.modules stubs for the package at import time, so the package-level name is
        a stub for every test collected after it.
        """
        from agno.knowledge.knowledge import Knowledge

        assert Knowledge().max_results == DEFAULT_MAX_RESULTS
