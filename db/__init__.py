from agno.db.postgres import PostgresDb

from db.session import get_db_url_cached


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
