"""HeX startup loads no knowledge; it only reports whether vector search is indexed (#42)."""

import logging

import pytest

from api.project_configs import hex_gig_config


@pytest.fixture
def startup(monkeypatch):
    monkeypatch.setattr(hex_gig_config, "require_knowledge", lambda agent: object())
    monkeypatch.setattr(hex_gig_config, "pgvector_of", lambda knowledge: object())

    async def run(problems):
        if isinstance(problems, Exception):

            def check(vector_db):
                raise problems

        else:

            def check(vector_db):
                return problems

        monkeypatch.setattr(hex_gig_config, "vector_schema_problems", check)
        await hex_gig_config.HexGigConfig().load_knowledge([object()])  # type: ignore[list-item]

    return run


@pytest.mark.asyncio
async def test_missing_index_is_logged_as_an_error(startup, caplog):
    with caplog.at_level(logging.ERROR):
        await startup(["ai.hex_gig_embeddings has no HNSW index"])

    assert "has no HNSW index" in caplog.text


@pytest.mark.asyncio
async def test_an_unreachable_database_does_not_stop_startup(startup, caplog):
    with caplog.at_level(logging.ERROR):
        await startup(ConnectionError("db down"))

    assert "Could not check the HeX vector table" in caplog.text


@pytest.mark.asyncio
async def test_ready_table_logs_no_error(startup, caplog):
    with caplog.at_level(logging.ERROR):
        await startup([])

    assert caplog.records == []
