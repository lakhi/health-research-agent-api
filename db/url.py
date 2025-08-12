from os import getenv

def get_db_url() -> str:
    # Standard connection (for local development)
    db_driver = getenv("DB_DRIVER", "postgresql+psycopg2")
    db_user = getenv("DB_USER")
    db_pass = getenv("DB_PASS")
    db_host = getenv("DB_HOST")
    db_port = getenv("DB_PORT")
    db_database = getenv("DB_DATABASE")

    base_url = f"{db_driver}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_database}"

    # if "azure" in db_host:
    #     # Azure PostgreSQL connection
    #     db_driver = "postgresql+psycopg2"
    #     ssl_mode = "?sslmode=require"

    #     base_url

    return base_url
