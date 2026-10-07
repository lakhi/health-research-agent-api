"""The pgvector layout the knowledge bases search against: halfvec column, HNSW index, own engine.

Why this exists (issue #42): agno creates its table as ``vector(1536)`` and never builds a vector
index — it only does so in ``PgVector.optimize()``, which nothing calls. Every search was a
sequential scan over the whole table, and on the B1ms server's 120-IOPS disk a cold scan took
45-85 s. An HNSW index cuts a cold search to ~5 s by reading ~540 pages instead of ~36,000.

Three things have to be true for that index to help, and agno guarantees none of them:

* **It has to exist.** A hand-made index was dropped by the v3 reset and nothing rebuilt it, so the
  index is created here, by code, and the API checks for it at startup.
* **It has to fit in memory.** ``halfvec(1536)`` stores the same 1,536 values in 16 bits each, so
  the index is ~103 MB instead of ~207 MB and fits in the 256 MB of ``shared_buffers``. Its top-50
  matched an exact ``vector`` scan in testing. It is also the only type that can be HNSW-indexed
  above 2,000 dimensions, so a later move to 3,072 is a dimension change, not a type change.
* **It has to be searched properly.** agno's default ``HNSW()`` sets ``ef_search = 5`` before every
  query, which cut recall@50 to 50% on the worst test query; callers pass ``ef_search`` explicitly.
  Filtered searches also need ``hnsw.iterative_scan``, without which pgvector post-filters a fixed
  candidate list and can return almost nothing (the SSC "no documents found" bug).

agno's SQL works unchanged against a halfvec column: pgvector's SQLAlchemy type binds the query
vector as an untyped ``'[...]'`` literal, which Postgres resolves to the halfvec operator.
"""

import logging
from typing import Any

from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector
from pgvector.sqlalchemy import Vector
from sqlalchemy import Table, text
from sqlalchemy.engine import Engine, create_engine

logger = logging.getLogger(__name__)

# Applied as a libpq startup option, so it holds for the whole session. Setting it with a SET
# statement on connect would sit inside psycopg2's implicit transaction and be undone by the
# rollback SQLAlchemy issues when a connection goes back to the pool. relaxed_order is enough:
# the reranker reorders every candidate anyway.
ITERATIVE_SCAN_OPTION = "-c hnsw.iterative_scan=relaxed_order"

# Pooled connections die silently behind Azure's network (13 and 21 Sep 2026: "SSL connection has
# been closed unexpectedly", which agno turns into an empty search result). pre_ping replaces a
# dead connection before it is used; recycling keeps connections younger than idle timeouts.
POOL_RECYCLE_SECONDS = 1800

# Building the index needs room for the whole graph; 256 MB holds a halfvec(1536) index of the
# current corpus on the 2 GB B1ms without spilling. Set for the building session only.
INDEX_BUILD_MAINTENANCE_WORK_MEM = "256MB"

HNSW_M = 16
HNSW_EF_CONSTRUCTION = 64


class HalfVector(Vector):
    """``Vector`` that creates its column as ``HALFVEC(n)``.

    Only the DDL changes. Binding and result parsing are inherited, so values still go in as
    ``'[...]'`` strings and come back as lists of floats — which is what agno's ``Document``
    expects. pgvector's own ``HALFVEC`` type would hand back ``HalfVector`` objects instead.
    """

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        if self.dim is None:
            return "HALFVEC"
        return f"HALFVEC({self.dim})"


class HalfvecPgVector(PgVector):
    """``PgVector`` whose table is created with a ``halfvec`` embedding column."""

    def get_table_v1(self) -> Table:
        table = super().get_table_v1()
        table.c.embedding.type = HalfVector(self.dimensions)
        return table


def pgvector_of(knowledge: Knowledge) -> PgVector:
    """The knowledge base's vector store, which these helpers only know how to manage as PgVector."""
    vector_db = knowledge.vector_db
    if not isinstance(vector_db, PgVector):
        raise TypeError(f"Expected a PgVector store, got {type(vector_db).__name__}")
    return vector_db


def create_vector_engine(db_url: str) -> Engine:
    """Engine for vector search: dead pooled connections replaced, iterative scans on."""
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=POOL_RECYCLE_SECONDS,
        connect_args={"options": ITERATIVE_SCAN_OPTION},
    )


def hnsw_index_name(table_name: str) -> str:
    return f"idx_{table_name}_embedding_hnsw"


def _embedding_column_type(conn: Any, schema: str, table_name: str) -> str | None:
    """The embedding column's type as Postgres prints it, e.g. ``halfvec(1536)``; None if absent."""
    return conn.execute(
        text(
            "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :schema AND c.relname = :table AND a.attname = 'embedding' AND NOT a.attisdropped"
        ),
        {"schema": schema, "table": table_name},
    ).scalar()


def _hnsw_index_exists(conn: Any, schema: str, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE schemaname = :schema AND tablename = :table "
                "AND indexdef ILIKE '%USING hnsw%' LIMIT 1"
            ),
            {"schema": schema, "table": table_name},
        ).scalar()
    )


def ensure_vector_schema(vector_db: PgVector) -> None:
    """Make the table halfvec and HNSW-indexed. Idempotent; run by the ingestion job, not the API.

    Converts a ``vector`` column left by plain agno in place (no re-embed), then builds the index
    if it is missing. Building after the bulk load is faster and gives a better graph than growing
    the index one insert at a time.
    """
    vector_db.create()
    schema, table_name = vector_db.schema, vector_db.table_name
    qualified = f'"{schema}"."{table_name}"'
    dimensions = vector_db.dimensions

    with vector_db.db_engine.begin() as conn:
        column_type = _embedding_column_type(conn, schema, table_name)
        if column_type is not None and column_type.startswith("vector"):
            logger.info("Converting %s.embedding from %s to halfvec(%d)", qualified, column_type, dimensions)
            conn.execute(
                text(
                    f"ALTER TABLE {qualified} ALTER COLUMN embedding "
                    f"TYPE halfvec({dimensions}) USING embedding::halfvec({dimensions})"
                )
            )

        if _hnsw_index_exists(conn, schema, table_name):
            return

        logger.info("Building HNSW index on %s (m=%d, ef_construction=%d)", qualified, HNSW_M, HNSW_EF_CONSTRUCTION)
        conn.execute(text(f"SET LOCAL maintenance_work_mem = '{INDEX_BUILD_MAINTENANCE_WORK_MEM}'"))
        # Single-threaded on purpose. A parallel build holds the graph in POSIX shared memory, which
        # failed in Docker's 64 MB /dev/shm ("could not resize shared memory segment"); a serial
        # build uses ordinary memory, and the 1-vCore B1ms gains nothing from parallel workers.
        conn.execute(text("SET LOCAL max_parallel_maintenance_workers = 0"))
        conn.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS "{hnsw_index_name(table_name)}" ON {qualified} '
                f"USING hnsw (embedding halfvec_cosine_ops) "
                f"WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION})"
            )
        )


def vector_schema_problems(vector_db: PgVector) -> list[str]:
    """What stands between this table and indexed search; empty when it is ready.

    Read-only. The API calls it at startup so a missing index is logged loudly rather than
    discovered as minute-long answers, which is how the September loss went unnoticed.
    """
    schema, table_name = vector_db.schema, vector_db.table_name
    with vector_db.db_engine.connect() as conn:
        column_type = _embedding_column_type(conn, schema, table_name)
        if column_type is None:
            return [f"{schema}.{table_name} does not exist yet; run the knowledge sync job"]
        problems = []
        if not column_type.startswith("halfvec"):
            problems.append(f"{schema}.{table_name}.embedding is {column_type}, expected halfvec")
        if not _hnsw_index_exists(conn, schema, table_name):
            problems.append(f"{schema}.{table_name} has no HNSW index, so every search is a full table scan")
        return problems
