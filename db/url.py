from os import getenv


def get_db_url() -> str:
    # Check if we're using Cloud SQL
    cloud_sql_connection_name = getenv("CLOUD_SQL_CONNECTION_NAME")
    
    if cloud_sql_connection_name:
        # Cloud SQL connection via Unix socket (for Cloud Run)
        db_user = getenv("DB_USER")
        db_pass = getenv("DB_PASS")
        db_database = getenv("DB_DATABASE")
        
        return "postgresql+psycopg://{}:{}@/{}?host=/cloudsql/{}".format(
            db_user,
            db_pass,
            db_database,
            cloud_sql_connection_name,
        )
    else:
        # Standard connection (for local development)
        db_driver = getenv("DB_DRIVER", "postgresql+psycopg")
        db_user = getenv("DB_USER")
        db_pass = getenv("DB_PASS")
        db_host = getenv("DB_HOST")
        db_port = getenv("DB_PORT")
        db_database = getenv("DB_DATABASE")
        return "{}://{}{}@{}:{}/{}".format(
            db_driver,
            db_user,
            f":{db_pass}" if db_pass else "",
            db_host,
            db_port,
            db_database,
        )
