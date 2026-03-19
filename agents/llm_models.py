from enum import Enum


class LLMModel(str, Enum):
    """Enum for LLM model types used across agents."""

    GPT_4_1 = "gpt-4.1"
    GPT_4O = "gpt-4o"
    GPT_5_CHAT = "gpt-5-chat"


VAX_STUDY_GPT_MODEL: str = LLMModel.GPT_4_1
