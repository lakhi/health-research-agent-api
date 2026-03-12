-- =============================================================================
-- Migration: Create daily_nex_agent_usage table
-- =============================================================================
-- 
-- Description:
--   Creates the table for tracking daily token usage and costs for the
--   nex agent budget enforcement system.
--
-- Usage:
--   psql -d <database_name> -f create_daily_nex_agent_usage.sql
--
-- =============================================================================

-- Create the table
CREATE TABLE IF NOT EXISTS daily_nex_agent_usage (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_eur FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create index for efficient date-based queries
CREATE INDEX IF NOT EXISTS ix_daily_nex_usage_date 
ON daily_nex_agent_usage(date);

-- Add comment to table
COMMENT ON TABLE daily_nex_agent_usage IS 
'Tracks daily token usage and costs for the nex agent budget enforcement';

-- Verify table creation
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'daily_nex_agent_usage'
ORDER BY ordinal_position;

select * from daily_nex_agent_usage dhcu ;