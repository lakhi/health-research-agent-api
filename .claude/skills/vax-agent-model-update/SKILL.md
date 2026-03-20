---
name: vax-agent-model-update
description: "Update VAX study agent model wiring for Azure OpenAI. Use when switching model deployments (for example to gpt-5-mini), updating AZURE_OPENAI_ENDPOINT, adding a model enum in llm_models.py, and updating the VAX_STUDY_GPT_MODEL constant."
argument-hint: "AZURE_OPENAI_ENDPOINT=<azure-endpoint> MODEL_ID=<azure-model-id>"
user-invocable: true
---

# VAX Agent Model Update

Update model configuration for the VAX study agents with explicit Azure OpenAI wiring.

## Inputs

Required inputs:

- `AZURE_OPENAI_ENDPOINT`: Azure endpoint URL for chat completions deployment.
- `MODEL_ID`: AzureOpenAI model id to use in agent constructors (example: `gpt-5-mini`).

## Files Updated

- `.env`
- `agents/llm_models.py`

## Procedure

1. Validate input format.

- Ensure `AZURE_OPENAI_ENDPOINT` is non-empty and starts with `https://`.
- Ensure `MODEL_ID` is non-empty and compatible with Agno AzureOpenAI id usage.

2. Update endpoint in `.env`.

- Replace only the `AZURE_OPENAI_ENDPOINT=` line with the provided value.
- Do not modify embedder env vars unless requested.

3. Ensure model enum exists in `agents/llm_models.py`.

- Convert `MODEL_ID` into an enum key using uppercase snake case.
- Example: `gpt-5-mini` -> `GPT_5_MINI = "gpt-5-mini"`.
- If enum value already exists, reuse it.
- Preserve existing enum members.

4. Update `VAX_STUDY_GPT_MODEL` in `agents/llm_models.py` to point to the new enum key. All vax agent factory defaults and `selector.py` import this constant and will follow automatically.

5. Keep explicit model assignment in Agent construction.

- Keep `model=AzureOpenAI(id=model_id)` in all agents.
- Never set the Agent model to unspecified or `None`.

6. Validate consistency.

- Verify `VAX_STUDY_GPT_MODEL` in `agents/llm_models.py` equals the target enum value.
- Verify `.env` contains the requested endpoint value.

7. Report outcome.

- Summarize changed files.
- State whether enum was created or reused.
- State whether endpoint changed.

## Decision Rules

- If the endpoint value in `.env` already matches input, do not rewrite unrelated lines.
- If enum key name conflicts with an existing different value, add a distinct key and keep both.
- If requested model change targets only VAX study, do not modify NEX agent defaults unless explicitly asked.

## Quality Checks

- Minimal diff only in listed files.
- No unrelated refactoring.
- Preserve runtime behavior besides intended model switch.
- Keep Azure model wiring explicit.

## References

- Agno Azure OpenAI overview: https://docs.agno.com/models/providers/cloud/azure-openai/overview
