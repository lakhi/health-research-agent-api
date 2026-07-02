-- =============================================================================
-- Migration: Add anonymous_user_id column to agent_usage_metrics
-- =============================================================================
--
-- Description:
--   Adds the longer-lived anonymous user identifier (browser localStorage UUID)
--   for per-user aggregation (issue #27). Idempotent — safe to re-run.
--   Historical rows keep NULL and are excluded from per-user report queries.
--
-- Usage:
--   psql -d <database_name> -f add_anonymous_user_id_column.sql
--
-- =============================================================================

ALTER TABLE agent_usage_metrics
    ADD COLUMN IF NOT EXISTS anonymous_user_id VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_agent_usage_metrics_user
    ON agent_usage_metrics (anonymous_user_id);

-- Verify
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'agent_usage_metrics'
  AND column_name = 'anonymous_user_id';
