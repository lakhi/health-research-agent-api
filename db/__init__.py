from agno.db.postgres import PostgresDb
from db.session import db_url

control_agent_db = PostgresDb(
    db_url=db_url,
    session_table="control_agent_sessions",
)

simple_language_db = PostgresDb(
    db_url=db_url,
    session_table="simple_language_sessions",
)

simple_cat_lg_db = PostgresDb(
    db_url=db_url,
    session_table="simple_cat_lg_sessions",
)

healthsoc_agent_db = PostgresDb(
    db_url=db_url,
    session_table="healthsoc_agent_sessions",
)


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
        db_url=db_url,
        session_table=f"{project_name}_agentos_sessions",
    )
