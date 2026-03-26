from agno.db.postgres import PostgresDb

from db.session import get_db_url_cached


class _LazyPostgresDb:
    """Create PostgresDb instances only when first used."""

    def __init__(self, session_table: str):
        self._session_table = session_table
        self._db: PostgresDb | None = None

    def _get_db(self) -> PostgresDb:
        if self._db is None:
            self._db = PostgresDb(
                db_url=get_db_url_cached(),
                session_table=self._session_table,
            )
        return self._db

    def __getattr__(self, item):
        return getattr(self._get_db(), item)


control_agent_db = _LazyPostgresDb(session_table="control_agent_sessions")

simple_language_db = _LazyPostgresDb(session_table="simple_language_sessions")

simple_cat_lg_db = _LazyPostgresDb(session_table="simple_cat_lg_sessions")

# TODO: Remove after confirming session storage is permanently disabled
# nex_agent_db = PostgresDb(
#     db_url=db_url,
#     session_table="nex_agent_sessions",
# )


def get_project_db(project_name: str) -> PostgresDb:
    """
    Get unified database for AgentOS based on project name.
    This db propagates to all agents/teams/workflows without their own db.

    Args:
        project_name: The name of the active project

    Returns:
        PostgresDb instance configured for the project
    """
    return PostgresDb(
        db_url=get_db_url_cached(),
        session_table=f"{project_name}_agentos_sessions",
    )
