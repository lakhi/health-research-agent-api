# CLAUDE.md — health-research-agent-api

FastAPI-based multi-project health research agent platform for the University of Vienna Health Research Network. Supports two projects: **vax-study** and **nex**.

## Commands

### Requirements
```bash
./scripts/generate_requirements.sh           # pin current deps
./scripts/generate_requirements.sh upgrade   # upgrade all deps
./scripts/generate_requirements.sh linux     # Linux-compatible pins
./scripts/generate_requirements.sh linux-upgrade
```

### Environment switching
```bash
./scripts/switch_env.sh local   # symlinks .env → .env.local
./scripts/switch_env.sh azure   # symlinks .env → .env.azure
```

### Dev setup
```bash
./scripts/dev_setup.sh
source .venv/bin/activate
```

### Run
```bash
docker compose up -d                          # recommended
uvicorn api.main:app --reload                 # local without Docker
```

### Test
```bash
pytest tests/ -v
pytest tests/ -v --cov=api --cov-report=term-missing
pytest tests/ -v -m "not integration"        # skip integration tests
pytest tests/ -v -m integration              # integration tests only
```

### Lint / format
```bash
ruff format .
ruff check --fix .
ruff check .
mypy . --config-file pyproject.toml
```

## Architecture

### Multi-project factory pattern
`PROJECT_NAME` env var → `ProjectConfigFactory` (in `api/project_config.py`) → returns either `VaxStudyConfig` or `NexConfig`. Each config class handles agent initialisation, knowledge loading, and CORS origins for its project.

### Agent dispatch
`agents/selector.py` maps `AgentType` enum values to concrete agent instances. Agents are constructed with project-specific settings from the active config.

### Knowledge / RAG
- **NEX**: CSV product catalogue, hybrid search (BM25 + semantic) via Agno + pgvector.
- **VAX**: PDF vaccine-information catalogs, semantic search via Agno + pgvector.

### Budget enforcement (NEX only)
`services/budget_service.py` enforces a daily EUR spend limit. Timezone is `Europe/Vienna`.

### Database
- Lazy initialisation via `_LazyPostgresDb` in `db/__init__.py` — connection is not opened until first use.
- Agno auto-creates per-agent session tables in PostgreSQL.

## Key config & patterns

| Concern | Location |
|---|---|
| App settings (env vars) | `api/settings.py` — Pydantic `BaseSettings` |
| Azure OpenAI model IDs | `agents/llm_models.py` |
| Env files | `.env.local` / `.env.azure` (switched via `switch_env.sh`, symlinked to `.env`) |
| Ruff | line-length = 120 |
| mypy | strict mode; pgvector and agno modules are ignored |
| pytest-asyncio | `asyncio_mode = auto` |
| Integration test marker | `@pytest.mark.integration` |
