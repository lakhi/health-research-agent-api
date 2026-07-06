import os
from enum import Enum

from agno.models.openai import OpenAILike


class LLMModel(str, Enum):
    """Enum for LLM model types used across agents."""

    GPT_4_1 = "gpt-4.1"
    GPT_4O = "gpt-4o"
    GPT_5_CHAT = "gpt-5-chat"
    GPT_5_MINI = "gpt-5-mini-nex"


VAX_STUDY_GPT_MODEL: str = LLMModel.GPT_4_1


def get_vax_local_model(temperature: float = 0.2) -> OpenAILike:
    """Local model served via the Xinity OpenAI-compatible gateway (vax local-model experiment).

    The model specifier is deployment configuration owned by Xinity, so it is read from the
    environment alongside the gateway credentials rather than pinned in LLMModel.
    Read via os.getenv (not api.settings) because api.settings imports the project configs,
    which import the agent modules.
    """
    base_url = os.getenv("XINITY_BASE_URL")
    api_key = os.getenv("XINITY_API_KEY")
    model_id = os.getenv("XINITY_MODEL")

    if not (base_url and api_key and model_id):
        provided = {"XINITY_BASE_URL": base_url, "XINITY_API_KEY": api_key, "XINITY_MODEL": model_id}
        missing = ", ".join(name for name, value in provided.items() if not value)
        raise RuntimeError(f"Missing Xinity gateway environment variables: {missing}")

    return OpenAILike(id=model_id, base_url=base_url, api_key=api_key, temperature=temperature)
