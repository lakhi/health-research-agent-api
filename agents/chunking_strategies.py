from enum import Enum


class ChunkingStrategy(Enum):
    """Enum for document chunking strategies used in knowledge bases."""

    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"

    @property
    def chunk_size(self) -> int:
        """Get the default chunk size for this strategy."""
        if self == ChunkingStrategy.FIXED_SIZE:
            return 1200
        elif self == ChunkingStrategy.SEMANTIC:
            return 1000
        else:
            return 1200  # fallback default
