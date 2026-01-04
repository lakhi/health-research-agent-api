import os
from agno.knowledge.embedder.azure_openai import AzureOpenAIEmbedder
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# Centralized embedder instances for use across knowledge bases
azure_embedder = AzureOpenAIEmbedder(
    id="text-embedding-3-large",
    api_key=os.getenv("AZURE_EMBEDDER_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_EMBEDDER_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_EMBEDDER_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_EMBEDDER_DEPLOYMENT"),
)

sentence_transformer_embedder = SentenceTransformerEmbedder()