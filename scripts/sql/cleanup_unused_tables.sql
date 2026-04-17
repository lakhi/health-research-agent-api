-- =============================================================================
-- Database Cleanup: Remove Unused Tables 
-- =============================================================================
--
-- Description:
--   This migration script removes database tables that are no longer used by
--   the Health Research Agent API application. These tables were identified by
--   scanning the entire codebase to find all table references.
--
--   USED TABLES (DO NOT DELETE):
--   - control_agent_sessions
--   - simple_language_sessions
--   - vax-study_agentos_sessions
--   - nex_agentos_sessions
--   - marhino_normal_catalog
--   - marhino_catalog_contents
--   - nex_embeddings
--   - nex_contents
--   - daily_agent_usage        (renamed from daily_nex_agent_usage)
--   - agent_usage_metrics      (renamed from nex_agent_usage_metrics)
--
-- UNUSED TABLES (TO BE DELETED):
--   - virus_knowledge
--   - agno_eval_runs
--   - agno_memories
--   - agno_metrics
--   - agno_knowledge
--   - virus_normal_catalog
--   - agno_schema_versions
--   - virus_simple_catalog
--   - nex_agent_sessions
--   - healthsoc_agent_sessions
--   - healthsoc_agentos_sessions
--   - healthsoc_embeddings
--   - healthsoc_contents
--   - daily_healthsoc_chatbot_usage
--   - hrn_embeddings
--   - hrn_contents
--   - research_papers
--   - virus_knowledge_normal
--   - agno_sessions
--   - normal_catalog_contents
--   - virus_knowledge_simple
--   - simple_cat_lg_sessions   (deleted: simple_catalog_language agent removed)
--   - marhino_simple_catalog   (deleted: simple_catalog_language agent removed)
--
-- Usage:
--   psql -d <database_name> -f cleanup_unused_tables.sql
--
-- WARNING:
--   This script will permanently delete tables and all their data.
--   Ensure you have a backup before running this in production.
--
-- =============================================================================


-- Helper function to safely drop table if it exists
CREATE OR REPLACE FUNCTION drop_table_if_exists(table_name text) RETURNS void AS
$$
BEGIN
    EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', table_name);
    RAISE NOTICE 'Dropped table: %', table_name;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not drop table %: %', table_name, SQLERRM;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- PHASE 1: Drop unused agno framework tables
-- =============================================================================

SELECT drop_table_if_exists('agno_sessions');
SELECT drop_table_if_exists('agno_eval_runs');
SELECT drop_table_if_exists('agno_memories');
SELECT drop_table_if_exists('agno_metrics');
SELECT drop_table_if_exists('agno_knowledge');
SELECT drop_table_if_exists('agno_schema_versions');


-- =============================================================================
-- PHASE 2: Drop unused virus study tables
-- =============================================================================

SELECT drop_table_if_exists('virus_knowledge');
SELECT drop_table_if_exists('virus_normal_catalog');
SELECT drop_table_if_exists('virus_simple_catalog');
SELECT drop_table_if_exists('virus_knowledge_normal');
SELECT drop_table_if_exists('virus_knowledge_simple');


-- =============================================================================
-- PHASE 3: Drop unused catalog-related tables
-- =============================================================================

SELECT drop_table_if_exists('normal_catalog_contents');


-- =============================================================================
-- PHASE 4: Drop unused research and nex tables
-- =============================================================================

SELECT drop_table_if_exists('research_papers');
SELECT drop_table_if_exists('nex_agent_sessions');
SELECT drop_table_if_exists('healthsoc_agent_sessions');
SELECT drop_table_if_exists('healthsoc_agentos_sessions');
SELECT drop_table_if_exists('healthsoc_embeddings');
SELECT drop_table_if_exists('healthsoc_contents');
SELECT drop_table_if_exists('daily_healthsoc_chatbot_usage');
SELECT drop_table_if_exists('hrn_embeddings');
SELECT drop_table_if_exists('hrn_contents');


-- =============================================================================
-- PHASE 4b: Drop tables orphaned by removing the simple_catalog_language agent
-- =============================================================================

SELECT drop_table_if_exists('simple_cat_lg_sessions');
SELECT drop_table_if_exists('marhino_simple_catalog');


-- =============================================================================
-- PHASE 5: Rename budget/metrics tables to generic names
-- =============================================================================
-- These were renamed from NEX-specific to deployment-agnostic names when
-- SSC-PSYCH was added as a second budgeted project.

ALTER TABLE IF EXISTS daily_nex_agent_usage RENAME TO daily_agent_usage;
ALTER TABLE IF EXISTS nex_agent_usage_metrics RENAME TO agent_usage_metrics;

-- Rename indexes to match new table names
ALTER INDEX IF EXISTS ix_daily_nex_usage_date RENAME TO ix_daily_agent_usage_date;
ALTER INDEX IF EXISTS ix_nex_usage_metrics_date RENAME TO ix_agent_usage_metrics_date;
ALTER INDEX IF EXISTS ix_nex_usage_metrics_session RENAME TO ix_agent_usage_metrics_session;


-- =============================================================================
-- Cleanup: Drop the helper function
-- =============================================================================

DROP FUNCTION IF EXISTS drop_table_if_exists(text);


-- =============================================================================
-- Verification: List remaining tables
-- =============================================================================

SELECT
    schemaname,
    tablename
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename;

COMMENT ON DATABASE postgres IS 'Cleanup completed: Removed 23 unused tables and renamed 2 budget/metrics tables in health research agent API';
