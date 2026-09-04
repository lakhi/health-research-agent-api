"""Non-destructive Agno v2 -> v3 database migration, with a verification gate.

NOT USED BY THIS REPO'S MIGRATION. We reset instead — see scripts/sql/reset_agno_v3.sql
for why (no project needed its existing rows, and dropping sidesteps both the missing
pgvector `user_id` column and v3's metadata-aware content hashing). This script is kept as
the documented alternative: it is what to run against a database whose history must be
preserved, including any deployment discovered later that this migration missed.

What MigrationManager(db).up() does, per Agno's v3 guide:

  * copies each session's `runs` JSON blob into individual rows in the runs table,
    leaving the legacy column in place as a backup;
  * adds `user_id` columns and indexes to the evals, components, knowledge, schedules,
    schedule-runs and metrics tables, and re-keys user-namespaced entity learnings.

It is idempotent and non-destructive: reads keep working before, during and after, and
re-running never duplicates runs.

This script deliberately stops after verifying. It does not call
cleanup_legacy_runs_column(), which permanently deletes the legacy blob — the only copy of
the history if the migration did not in fact copy it. Reclaiming that storage is a separate,
manual decision to be taken only once the runs below look right AND the migrated history has
been eyeballed in the UI:

    db.cleanup_legacy_runs_column(force=True)   # NOT run here, on purpose

Usage:
    PROJECT_NAME=hex-gig python scripts/migrate_to_agno_v3.py

Refs #46
"""

import asyncio
import sys

from agno.db.migrations.manager import MigrationManager

from api.settings import api_settings
from db import get_project_db


def main() -> int:
    project_name = api_settings.project_config.project_name

    # Built exactly as the app builds it, so the migration lands on the same tables the
    # running deployment reads — including the per-project session/runs table names.
    db = get_project_db(project_name)

    print(f"Migrating Agno tables for project: {project_name}")
    asyncio.run(MigrationManager(db).up())

    runs = db.get_runs(limit=5)
    assert len(runs) > 0, "Migration copied nothing - do NOT run cleanup"

    print(
        f"Migration verified ({len(runs)} run(s) readable from the runs table).\n"
        "Confirm the history looks right in the UI, then reclaim the legacy blob manually "
        "with db.cleanup_legacy_runs_column(force=True). Nothing here deletes it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
