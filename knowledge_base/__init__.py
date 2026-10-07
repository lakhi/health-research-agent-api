import os

from agno.knowledge.embedder.azure_openai import AzureOpenAIEmbedder


# Chunks per embedding request when batching. Average HeX chunks are ~100 tokens, so a request
# stays far below the per-request and per-minute token limits even for the longest chunks.
EMBEDDING_BATCH_SIZE = 50


def get_azure_embedder(enable_batch: bool = False) -> AzureOpenAIEmbedder:
    """
    Get a configured Azure OpenAI embedder.
    This is called after load_dotenv() so env vars are available.

    enable_batch: embed many chunks per request during ingestion. Without it agno embeds every
    chunk of a document as its own concurrent request; a 300-chunk paper opened hundreds of
    connections at once and the OpenAI client's 5 s connect timeout turned that burst into
    "Request timed out" on whole documents (local loads 13 Sep and 7 Oct, prod 23 Sep, #42).
    Batching gives identical vectors with a handful of requests. Searches embed a single query
    and are unaffected.

    Returns:
        AzureOpenAIEmbedder configured with environment variables
    """
    # api_version is typed `str` on AzureOpenAIEmbedder and carries its own default, so passing
    # os.getenv(...) straight through overrode that default with None whenever the var was unset.
    # Every deployed environment sets it; fall back to agno's own default rather than to None.
    api_version = os.getenv("AZURE_EMBEDDER_OPENAI_API_VERSION") or AzureOpenAIEmbedder.api_version

    return AzureOpenAIEmbedder(
        id="text-embedding-3-large",
        # dimensions: left unset, so agno's default of 1536 applies to text-embedding-3-*.
        # This is NOT a pgvector storage limit — `vector` holds up to 16,000 dimensions,
        # and Azure honours the `dimensions` parameter on every api-version we run
        # (verified against 2023-05-15 and 2024-02-01). The 2,000-dimension cap applies
        # only to an HNSW index on a `vector` column; `halfvec` indexes up to 4,000.
        #
        # HeX already stores halfvec(1536) with an HNSW index (knowledge_base/vector_store.py),
        # so moving it to 3072 is a dimension change plus a full re-embed. The measured
        # retrieval gain over 1536 is ~1-4% relative, and 3072 doubles the index size; best
        # evaluated alongside a re-chunk, which needs a re-embed anyway (#47).
        api_key=os.getenv("AZURE_EMBEDDER_OPENAI_API_KEY"),
        api_version=api_version,
        azure_endpoint=os.getenv("AZURE_EMBEDDER_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_EMBEDDER_DEPLOYMENT"),
        enable_batch=enable_batch,
        batch_size=EMBEDDING_BATCH_SIZE,
    )
