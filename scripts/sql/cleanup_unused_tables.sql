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
--   - simple_cat_lg_sessions
--   - vax-study_agentos_sessions
--   - healthsoc_agentos_sessions
--   - marhino_normal_catalog
--   - marhino_simple_catalog
--   - marhino_catalog_contents
--   - healthsoc_embeddings
--   - healthsoc_contents
--   - daily_healthsoc_chatbot_usage
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
--   - healthsoc_agent_sessions
--   - research_papers
--   - virus_knowledge_normal
--   - agno_sessions
--   - normal_catalog_contents
--   - virus_knowledge_simple
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
-- PHASE 4: Drop unused research and healthsoc tables
-- =============================================================================

SELECT drop_table_if_exists('research_papers');
SELECT drop_table_if_exists('healthsoc_agent_sessions');


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

COMMENT ON DATABASE postgres IS 'Cleanup completed: Removed 14 unused tables from health research agent API';
