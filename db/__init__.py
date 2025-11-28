from agno.db.postgres import PostgresDb
from db.session import db_url

# PostgresDb instance for agent session storage
# Sessions are stored in the "control_agent_sessions" table
agent_db = PostgresDb(
    db_url=db_url,
    session_table="control_agent_sessions",
)
