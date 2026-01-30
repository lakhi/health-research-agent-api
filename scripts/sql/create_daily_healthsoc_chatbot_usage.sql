-- =============================================================================
-- Migration: Create daily_healthsoc_chatbot_usage table
-- =============================================================================
-- 
-- Description:
--   Creates the table for tracking daily token usage and costs for the
--   healthsoc chatbot budget enforcement system.
--
-- Usage:
--   psql -d <database_name> -f create_daily_healthsoc_chatbot_usage.sql
--
-- =============================================================================

-- Create the table
CREATE TABLE IF NOT EXISTS daily_healthsoc_chatbot_usage (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_eur FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create index for efficient date-based queries
CREATE INDEX IF NOT EXISTS ix_daily_healthsoc_usage_date 
ON daily_healthsoc_chatbot_usage(date);

-- Add comment to table
COMMENT ON TABLE daily_healthsoc_chatbot_usage IS 
'Tracks daily token usage and costs for the healthsoc chatbot budget enforcement';

-- Verify table creation
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'daily_healthsoc_chatbot_usage'
ORDER BY ordinal_position;
