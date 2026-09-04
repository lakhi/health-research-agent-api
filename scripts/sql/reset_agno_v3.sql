-- =============================================================================
-- Agno v2 -> v3: drop this project's Agno-managed tables so v3 recreates them
-- =============================================================================
--
-- Description:
--   Agno v3 changes the schema in three ways: session rows stop carrying their
--   run history as a JSON blob (each run becomes a row in a separate runs
--   table), the pgvector tables gain a `user_id` column and index, and Agno's
--   own bookkeeping tables gain `user_id` too.
--
--   Agno ships a non-destructive MigrationManager for this
--   (scripts/migrate_to_agno_v3.py). We do not use it: no project needs its
--   existing rows — the vax study is complete and its transcripts are already
--   exported, and hex-gig and ssc-psych are not yet live — so dropping is
--   simpler and avoids two edge cases entirely:
--
--     1. Pre-v3 pgvector tables have no `user_id`, and on schema-based stores
--        a user-scoped search against one raises ValueError rather than
--        returning empty.
--     2. v3's Knowledge._build_content_hash folds `metadata` into the dedupe
--        key. Every existing row therefore hashes differently under v3, so the
--        `skip_if_exists=True` loaders would stop recognising them, re-embed
--        everything, and leave the originals behind as duplicates.
--
--   The <project>_agentos_runs entries only exist once v3 has run (they are
--   what v3 normalises the sessions blob into), so on a first reset from v2 they
--   simply report "does not exist, skipping". They matter when re-resetting.
--
--   Agno recreates its tables at the v3 schema on the next startup
--   (auto_provision_dbs), and knowledge re-embeds from source: u:Cloud PDFs,
--   the RSS feed and the members CSV for hex-gig, the website scrape for
--   ssc-psych, the catalog PDF for vax-study.
--
-- Scope:
--   Every drop is commented out. Uncomment the section(s) for the database you
--   are actually connected to — that deliberate step is the safety gate on a
--   destructive script.
--
--   On Azure each project has its own database, so exactly one section applies
--   per connection. The local dev database (compose pgvector, `ai`) holds all
--   three projects at once, so a full local reset means uncommenting all of
--   them. The trailing SELECT lists what is present either way; run it first if
--   you are unsure which you are looking at.
--
-- NOT dropped (ours, not Agno's — they hold the usage history the
-- usage-report skill reads, and the reframing from issue #27):
--   - agent_usage_metrics
--   - daily_agent_usage
--
-- Usage:
--   psql -d <database_name> -f reset_agno_v3.sql
--   ...then uncomment the section for that database first.
--
-- WARNING:
--   Permanently deletes chat history and embeddings. The next startup does a
--   FULL re-embed, which is slow on a small instance (hex-gig runs B1ms) and
--   costs Azure OpenAI embedding calls. Take a backup if in any doubt.
--
--   Run this BEFORE first starting the v3 image against the database. Starting
--   v3 against a half-reset database leaves it in a mixed state: v3 creates the
--   tables that are missing, then fails schema validation on the stale ones.
--
-- Refs #46
-- =============================================================================


-- Schema-qualified drop, named distinctly from the 1-arg drop_table_if_exists in
-- cleanup_unused_tables.sql (a 2-arg overload beside it would just be confusing). That one takes
-- a bare name and so resolves against search_path; everything here lives in the
-- `ai` schema (both PostgresDb.db_schema and PgVector.schema default to it), so
-- the schema has to be explicit or the drops silently match nothing.
CREATE OR REPLACE FUNCTION drop_table_in_schema(schema_name text, table_name text) RETURNS void AS
$$
BEGIN
    EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE', schema_name, table_name);
    RAISE NOTICE 'Dropped table: %.%', schema_name, table_name;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not drop table %.%: %', schema_name, table_name, SQLERRM;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- hex-gig
-- =============================================================================
-- SELECT drop_table_in_schema('ai', 'hex-gig_agentos_sessions');
-- SELECT drop_table_in_schema('ai', 'hex-gig_agentos_runs');
-- SELECT drop_table_in_schema('ai', 'hex_gig_embeddings');
-- SELECT drop_table_in_schema('ai', 'hex_gig_contents');


-- =============================================================================
-- ssc-psych
-- =============================================================================
-- SELECT drop_table_in_schema('ai', 'ssc-psych_agentos_sessions');
-- SELECT drop_table_in_schema('ai', 'ssc-psych_agentos_runs');
-- SELECT drop_table_in_schema('ai', 'ssc_psych_embeddings');
-- SELECT drop_table_in_schema('ai', 'ssc_psych_contents');


-- =============================================================================
-- vax-study
-- =============================================================================
-- Transcripts were exported before this migration
-- (scripts/export_vax_study_sessions.py); the study is complete.
-- control_agent_sessions and simple_language_sessions are pre-launch testing
-- leftovers, ~19 rows total.
-- SELECT drop_table_in_schema('ai', 'vax-study_agentos_sessions');
-- SELECT drop_table_in_schema('ai', 'vax-study_agentos_runs');
-- SELECT drop_table_in_schema('ai', 'marhino_normal_catalog');
-- SELECT drop_table_in_schema('ai', 'marhino_catalog_contents');
-- SELECT drop_table_in_schema('ai', 'control_agent_sessions');
-- SELECT drop_table_in_schema('ai', 'simple_language_sessions');


-- =============================================================================
-- Agno bookkeeping tables — REQUIRED for every database, not optional
-- =============================================================================
-- Agno keeps its own tables alongside the per-project ones: agno_metrics,
-- agno_knowledge, agno_memories, agno_sessions, agno_eval_runs, agno_components,
-- agno_schedules and friends. They are not named per project, so the sections
-- above miss them, and they were created by v2 without the `user_id` column v3
-- expects.
--
-- This is not cosmetic. v3 validates the schema at startup, and a single stale
-- table fails the WHOLE PostgresDb:
--
--   WARNING  Missing columns {'user_id'} in table ai.agno_metrics
--   WARNING  Failed to initialize PostgresDb (id: ...): Table ai.agno_metrics
--            has an invalid schema ...
--
-- The app still answers requests, but its database is dead: no sessions, no
-- metrics. Dropping them lets v3 recreate them correctly.
--
-- agno_schema_versions goes too — a stale version row would make
-- MigrationManager treat a freshly created v3 table as already migrated.
--
-- The pattern escapes the underscore (`_` is a LIKE wildcard), so it matches
-- agno_* and nothing else: our agent_usage_metrics and daily_agent_usage, and
-- the per-project <project>_agentos_* tables, are all untouched.

-- DO $$
-- DECLARE
--     tbl text;
-- BEGIN
--     FOR tbl IN
--         SELECT table_name FROM information_schema.tables
--         WHERE table_schema = 'ai' AND table_name LIKE 'agno\_%'
--         ORDER BY table_name
--     LOOP
--         EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE', 'ai', tbl);
--         RAISE NOTICE 'Dropped Agno table: ai.%', tbl;
--     END LOOP;
-- END;
-- $$;


-- =============================================================================
-- Verify: after the drops, and again after the app has restarted
-- =============================================================================
-- Before restart, this should list only agent_usage_metrics / daily_agent_usage
-- (plus anything belonging to another project sharing the server).
-- After restart, the embeddings table should carry a `user_id` column and a
-- <project>_agentos_runs table should exist.

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('ai', 'public')
ORDER BY table_schema, table_name;
