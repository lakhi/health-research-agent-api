"""Load .env before any modules that read env vars at import time."""

import os

from dotenv import load_dotenv

load_dotenv(override=False)

# When running tests from the host machine, the pgvector Docker service is
# accessible at localhost (port-mapped). Override the Docker service name.
if os.environ.get("DB_HOST") == "pgvector":
    os.environ["DB_HOST"] = "localhost"

# compose.yaml remaps DB_PASSWORD→DB_PASS and DB_NAME→DB_DATABASE for the
# API container. Bridge those mappings when running tests directly on the host.
if not os.environ.get("DB_PASS") and os.environ.get("DB_PASSWORD"):
    os.environ["DB_PASS"] = os.environ["DB_PASSWORD"]
if not os.environ.get("DB_DATABASE") and os.environ.get("DB_NAME"):
    os.environ["DB_DATABASE"] = os.environ["DB_NAME"]
