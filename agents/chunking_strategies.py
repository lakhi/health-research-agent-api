from enum import Enum


class ChunkingStrategy(Enum):
    """Enum for document chunking strategies used in knowledge bases."""

    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"  # v2.3.17: Semantic chunking with custom embedder support
    RECURSIVE = "recursive"

    @property
    def chunk_size(self) -> int:
        """Get the default chunk size for this strategy."""
        if self == ChunkingStrategy.FIXED_SIZE:
            return 1200
        elif self == ChunkingStrategy.SEMANTIC:
            return 2000  # Optimized for scientific articles (10-20 pages)
        elif self == ChunkingStrategy.RECURSIVE:
            return 4000
        else:
            return 1200  # fallback default

    @property
    def similarity_threshold(self) -> float:
        """Get the default similarity threshold for semantic chunking."""
        if self == ChunkingStrategy.SEMANTIC:
            return 0.5  # Threshold for determining semantic breaks
        return 0.0  # Not applicable for non-semantic strategies
