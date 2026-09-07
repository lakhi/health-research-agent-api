from enum import Enum


class LLMModel(str, Enum):
    """Azure OpenAI model deployments used across agents.

    Keep this to models that still have a live Azure deployment. A value here is a
    label, not a selector: AZURE_OPENAI_ENDPOINT carries the full deployment path
    (.../deployments/<name>/chat/completions), so the env var is what actually picks
    the model. A stale entry therefore fails at request time — a retired model returns
    410 Gone — rather than at import, so it will not be caught by tests or startup.
    """

    GPT_4_1 = "gpt-4.1"
    GPT_5_MINI = "gpt-5-mini-nex"


VAX_STUDY_GPT_MODEL: str = LLMModel.GPT_4_1
