import sys
import time

from model2vec import StaticModel

MODEL = "minishlab/potion-base-32M"
MAX_ATTEMPTS = 5
RETRY_DELAY = 15

for attempt in range(MAX_ATTEMPTS):
    try:
        StaticModel.from_pretrained(MODEL)
        print(f"Model '{MODEL}' downloaded successfully.")
        sys.exit(0)
    except Exception as exc:
        print(f"Attempt {attempt + 1}/{MAX_ATTEMPTS} failed: {exc}")
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(RETRY_DELAY)

sys.exit(1)
