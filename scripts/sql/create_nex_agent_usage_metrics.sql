-- =============================================================================
-- Migration: Create nex_agent_usage_metrics table
-- =============================================================================
--
-- Description:
--   Creates the table for tracking anonymous per-request usage metrics
--   for the nex agent. Captures operational data (tokens, latency, cost,
--   status) without any message content or user identity.
--
-- Usage:
--   psql -d <database_name> -f create_nex_agent_usage_metrics.sql
--
-- =============================================================================

-- Create the table
CREATE TABLE IF NOT EXISTS nex_agent_usage_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    anonymous_session_id VARCHAR(64),
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    duration_seconds FLOAT,
    time_to_first_token FLOAT,
    cost_eur FLOAT NOT NULL DEFAULT 0.0,
    response_status VARCHAR(32) NOT NULL DEFAULT 'success',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS ix_nex_usage_metrics_date
ON nex_agent_usage_metrics(date);

CREATE INDEX IF NOT EXISTS ix_nex_usage_metrics_session
ON nex_agent_usage_metrics(anonymous_session_id);

-- Add comment to table
COMMENT ON TABLE nex_agent_usage_metrics IS
'Anonymous per-request usage metrics for the nex agent (no message content or user identity)';

-- Verify table creation
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'nex_agent_usage_metrics'
ORDER BY ordinal_position;
