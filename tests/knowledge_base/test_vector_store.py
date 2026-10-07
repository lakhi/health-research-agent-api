"""The vector-store layout the HeX knowledge base relies on for indexed search (#42)."""

from typing import Any

from agno.knowledge.embedder.openai import OpenAIEmbedder
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from knowledge_base import vector_store
from knowledge_base.vector_store import HalfVector, HalfvecPgVector, hnsw_index_name


def test_halfvector_creates_a_halfvec_column():
    assert HalfVector(1536).compile(dialect=postgresql.dialect()) == "HALFVEC(1536)"


def test_halfvector_keeps_vector_binding_so_agno_sql_works_unchanged():
    # agno binds the query vector through the column type; an untyped '[...]' literal is what
    # Postgres resolves to the halfvec operator, and lists are what agno's Document expects back.
    bind = HalfVector(3).bind_processor(postgresql.dialect())
    result = HalfVector(3).result_processor(postgresql.dialect(), None)

    assert bind([0.5, 0.25, 1.0]) == "[0.5,0.25,1.0]"
    assert list(result("[0.5,0.25,1]")) == [0.5, 0.25, 1.0]


def test_halfvec_pgvector_table_is_created_as_halfvec():
    store = HalfvecPgVector(
        table_name="hex_gig_embeddings",
        schema="ai",
        db_url="postgresql+psycopg2://user:pass@localhost:1/db",
        embedder=OpenAIEmbedder(dimensions=1536, api_key="unused"),
    )

    ddl = str(CreateTable(store.table).compile(dialect=postgresql.dialect()))

    assert "embedding HALFVEC(1536)" in ddl


def test_vector_engine_turns_on_pre_ping_and_iterative_scans(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(vector_store, "create_engine", lambda url, **kwargs: captured.update(url=url, **kwargs))

    vector_store.create_vector_engine("postgresql+psycopg2://user:pass@host/db")

    assert captured["pool_pre_ping"] is True
    assert captured["connect_args"] == {"options": "-c hnsw.iterative_scan=relaxed_order"}


def test_hnsw_index_name_is_stable():
    assert hnsw_index_name("hex_gig_embeddings") == "idx_hex_gig_embeddings_embedding_hnsw"
