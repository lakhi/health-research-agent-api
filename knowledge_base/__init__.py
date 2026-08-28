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
        # dimensions=3072, # Pgvector does not support 3072 dimension vectors, hence defaulting to 1536
        api_key=os.getenv("AZURE_EMBEDDER_OPENAI_API_KEY"),
        api_version=api_version,
        azure_endpoint=os.getenv("AZURE_EMBEDDER_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_EMBEDDER_DEPLOYMENT"),
    )
