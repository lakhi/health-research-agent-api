from enum import Enum


class LLMModel(str, Enum):
    """Enum for LLM model types used across agents."""

    GPT_4_1 = "gpt-4.1"
    GPT_5_CHAT = "gpt-5-chat"
