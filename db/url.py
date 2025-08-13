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

    if db_host and "azure" in db_host:
        ssl_mode = "?sslmode=require"
        base_url += ssl_mode

    print(f"Database URL: {base_url}")  # Debugging output

    return base_url
