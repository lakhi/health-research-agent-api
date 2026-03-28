-- =============================================================================
-- Agent Usage Reports
-- =============================================================================
--
-- Description:
--   Ready-to-run reporting queries for the agent usage metrics table.
--   All queries operate on aggregates — no individual message content is stored.
--
-- Usage:
--   psql -d <database_name> -f usage_reports.sql
--
--   For CSV export:
--   psql -d <database_name> -c "COPY (<query>) TO STDOUT CSV HEADER" > report.csv
--
-- Parameters (set with psql -v or \set):
--   :from_date - Start date (e.g., '2026-01-01')
--   :to_date   - End date (e.g., '2026-03-28')
--
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Unique sessions per period
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    COUNT(DISTINCT anonymous_session_id) AS unique_sessions,
    COUNT(*) AS total_requests
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
  AND anonymous_session_id IS NOT NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Session duration distribution
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    anonymous_session_id,
    COUNT(*) AS messages,
    MIN(created_at) AS first_message,
    MAX(created_at) AS last_message,
    ROUND(EXTRACT(EPOCH FROM MAX(created_at) - MIN(created_at))::numeric, 0) AS duration_seconds
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
  AND anonymous_session_id IS NOT NULL
GROUP BY anonymous_session_id
HAVING COUNT(*) > 1
ORDER BY duration_seconds DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Daily request volume and unique sessions
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COUNT(*) AS total_requests,
    COUNT(DISTINCT anonymous_session_id) AS unique_sessions,
    COUNT(*) FILTER (WHERE response_status = 'success') AS successful,
    COUNT(*) FILTER (WHERE response_status = 'error') AS errors,
    COUNT(*) FILTER (WHERE response_status = 'budget_exceeded') AS budget_exceeded
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Cost and token summary by date
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
    COALESCE(SUM(total_tokens), 0) AS total_tokens,
    ROUND(COALESCE(SUM(cost_eur), 0)::numeric, 4) AS total_cost_eur
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Peak usage hours (Vienna timezone)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    EXTRACT(HOUR FROM created_at AT TIME ZONE 'Europe/Vienna') AS hour_vienna,
    COUNT(*) AS requests,
    COUNT(DISTINCT anonymous_session_id) AS unique_sessions
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY hour_vienna
ORDER BY hour_vienna;


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Average response latency by date
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COUNT(*) AS requests,
    ROUND(AVG(duration_seconds)::numeric, 2) AS avg_duration_s,
    ROUND(AVG(time_to_first_token)::numeric, 3) AS avg_ttft_s,
    ROUND(MAX(duration_seconds)::numeric, 2) AS max_duration_s
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
  AND response_status = 'success'
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Error rate by date
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (WHERE response_status != 'success') AS non_success,
    ROUND(
        (COUNT(*) FILTER (WHERE response_status != 'success'))::numeric / NULLIF(COUNT(*), 0) * 100,
        1
    ) AS error_rate_pct
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. Weekly summary (for periodic reporting)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    DATE_TRUNC('week', date)::date AS week_start,
    COUNT(*) AS total_requests,
    COUNT(DISTINCT anonymous_session_id) AS unique_sessions,
    COALESCE(SUM(total_tokens), 0) AS total_tokens,
    ROUND(COALESCE(SUM(cost_eur), 0)::numeric, 4) AS total_cost_eur,
    ROUND(AVG(duration_seconds)::numeric, 2) AS avg_duration_s,
    COUNT(*) FILTER (WHERE response_status != 'success') AS non_success_count
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY week_start
ORDER BY week_start;
