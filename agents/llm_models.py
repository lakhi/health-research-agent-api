from enum import Enum


class LLMModel(str, Enum):
    """Enum for LLM model types used across agents."""
    
    GPT_4O = "gpt-4o"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
