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
