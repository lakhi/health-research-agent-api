# CLAUDE.md — health-research-agent-api

FastAPI-based multi-project health research agent platform for the University of Vienna Health Research Network. Supports three projects: **vax-study**, **hex_gig**, and **ssc-psych**.

## Commands

### Requirements
```bash
./scripts/generate_requirements.sh           # pin current deps
./scripts/generate_requirements.sh upgrade   # upgrade all deps
./scripts/generate_requirements.sh linux     # Linux-compatible pins
./scripts/generate_requirements.sh linux-upgrade
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
`PROJECT_NAME` env var → `ProjectConfigFactory` (in `api/project_configs/project_config_factory.py`) → returns `VaxStudyConfig`, `HexGigConfig`, or `SscPsychConfig`. Each config class handles agent initialisation, knowledge loading, and CORS origins for its project.

### Agent dispatch
`agents/registry.py` holds startup-built agents keyed by `AgentType` id. Agents are constructed with project-specific settings from the active config.

### Knowledge / RAG
- **HeX-GiG**: CSV member profiles + u:Cloud research PDFs + RSS news, semantic (vector) search via Agno + pgvector. (Was hybrid; agno's hybrid_search full-scans the table — see knowledge_base/hex_gig_knowledge_base.py.)
- **VAX**: PDF vaccine-information catalogs, semantic search via Agno + pgvector.
- **SSC-PSYCH**: Web-scraped SSC website pages + downloaded PDF forms/regulations, semantic (vector) search via Agno + pgvector.

Agno v3 folds an item's `metadata` into its content hash, so `skip_if_exists=True` no longer recognises an item whose metadata changed — it re-embeds it and leaves the old row behind as a duplicate. Editing the members CSV or a scraper's metadata therefore has a cost; drop and reload rather than relying on the skip.

### Budget enforcement
`services/budget_service.py` enforces a daily EUR spend limit per deployment. Timezone is `Europe/Vienna`. Applies to projects with budget env vars configured (HeX-GiG, SSC-PSYCH).

### Public surface
`api/security.py` refuses every request outside `GET /agents`, `POST /agents/{id}/runs`, `/health` and the docs routes. AgentOS mounts a large unauthenticated admin surface (`/sessions`, `/knowledge`, `/metrics`, `/learnings`, `/databases`, …) and these deployments have public ingress with no `OS_SECURITY_KEY`.

It is an **allow-list**, enforced as raw ASGI middleware. Do not turn it back into a prefix deny-list, and do not go back to filtering `app.router.routes`: that earlier approach broke silently when FastAPI 0.141 made `include_router` lazy (routes lost their `.path`, so nothing matched and everything stayed reachable). `tests/api/test_public_surface.py` guards both properties.

### Database
- Lazy initialisation: `get_db_url_cached()` and `_LazySessionLocal` in `db/session.py` defer engine/session creation, so no connection is opened at import time.
- `get_project_db()` in `db/__init__.py` names both `{project}_agentos_sessions` and `{project}_agentos_runs`; Agno auto-provisions those and its own bookkeeping tables in PostgreSQL, all in the `ai` schema.

## Key config & patterns

| Concern | Location |
|---|---|
| App settings (env vars) | `api/settings.py` — Pydantic `BaseSettings` |
| Azure OpenAI model IDs | `agents/llm_models.py` |
| Agno DB reset (v3 schema) | `scripts/sql/reset_agno_v3.sql` — run by hand, per database |
| Env files | single `.env` (gitignored, edited directly); `.env.example` documents required keys. Azure Container App env vars are set directly on the resource, independent of any local file |
| Ruff | line-length = 120 |
| mypy | strict mode; pgvector and agno modules are ignored |
| pytest-asyncio | `asyncio_mode = auto` |
| Integration test marker | `@pytest.mark.integration` |
