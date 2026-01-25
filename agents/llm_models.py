from enum import Enum


class LLMModel(str, Enum):
    """Enum for LLM model types used across agents."""

    GPT_4O = "gpt-4o"
    GPT_4_1 = "gpt-4.1"
