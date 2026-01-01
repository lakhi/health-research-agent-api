from agno.knowledge.embedder.azure_openai import AzureOpenAIEmbedder
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# Centralized embedder instances for use across knowledge bases
azure_embedder = AzureOpenAIEmbedder(id="text-embedding-3-large")

sentence_transformer_embedder = SentenceTransformerEmbedder()
