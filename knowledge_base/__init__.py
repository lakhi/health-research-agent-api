import os
from agno.knowledge.embedder.azure_openai import AzureOpenAIEmbedder
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder


def get_azure_embedder() -> AzureOpenAIEmbedder:
    """
    Get a configured Azure OpenAI embedder.
    This is called after load_dotenv() so env vars are available.

    Returns:
        AzureOpenAIEmbedder configured with environment variables
    """
    return AzureOpenAIEmbedder(
        id="text-embedding-3-large",
        # dimensions=3072, # Pgvector does not support 3072 dimension vectors, hence defaulting to 1536
        api_key=os.getenv("AZURE_EMBEDDER_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_EMBEDDER_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_EMBEDDER_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_EMBEDDER_DEPLOYMENT"),
    )


sentence_transformer_embedder = SentenceTransformerEmbedder()
