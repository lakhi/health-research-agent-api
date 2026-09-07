import os

from agno.knowledge.embedder.azure_openai import AzureOpenAIEmbedder


def get_azure_embedder() -> AzureOpenAIEmbedder:
    """
    Get a configured Azure OpenAI embedder.
    This is called after load_dotenv() so env vars are available.

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
        # only to HNSW/IVFFlat indexes, and nothing here builds one: agno creates a vector
        # index solely via PgVector.optimize(), which nothing in this repo calls.
        #
        # To move to 3072 the column has to become halfvec(3072) — identical bytes per row
        # to vector(1536), and HNSW-indexable up to 4,000 dimensions. That needs a PgVector
        # subclass overriding get_table_v1, pgvector >= 0.8 (iterative index scans, without
        # which a filtered ANN query drops most of its results), and a full re-embed. The
        # measured retrieval gain over 1536 is ~1-4% relative; a reranker is the cheaper win.
        api_key=os.getenv("AZURE_EMBEDDER_OPENAI_API_KEY"),
        api_version=api_version,
        azure_endpoint=os.getenv("AZURE_EMBEDDER_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_EMBEDDER_DEPLOYMENT"),
    )
