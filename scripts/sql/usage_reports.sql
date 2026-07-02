-- =============================================================================
-- Agent Usage Reports
-- =============================================================================
--
-- Description:
--   Ready-to-run reporting queries for the agent usage metrics table.
--   All queries operate on aggregates — no individual message content is stored.
--   "User" means one anonymous browser profile (localStorage UUID), not a
--   verified person; rows recorded before the user id existed are NULL and
--   excluded from per-user queries (8-10).
--
-- Usage:
--   psql -d <database_name> -f usage_reports.sql
--
--   For CSV export:
--   psql -d <database_name> -c "COPY (<query>) TO STDOUT CSV HEADER" > report.csv
--
-- Parameters (set with psql -v or \set):
--   :from_date    - Start date (e.g., '2026-01-01')
--   :to_date      - End date (e.g., '2026-03-28')
--   :daily_budget - Daily budget limit in EUR (e.g., 2.0), for budget_used_pct
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
-- 2. Session-size distribution: sessions bucketed by message count,
--    with the average session duration per bucket. Single-message sessions
--    fall back to the run duration so one-shot visitors aren't invisible.
-- ─────────────────────────────────────────────────────────────────────────────
WITH session_stats AS (
    SELECT
        anonymous_session_id,
        COUNT(*) AS messages,
        CASE
            WHEN COUNT(*) = 1 THEN COALESCE(MAX(duration_seconds), 0)
            ELSE EXTRACT(EPOCH FROM MAX(created_at) - MIN(created_at))
        END AS session_time_seconds
    FROM agent_usage_metrics
    WHERE date BETWEEN :from_date AND :to_date
      AND anonymous_session_id IS NOT NULL
    GROUP BY anonymous_session_id
)
SELECT
    CASE
        WHEN messages = 1 THEN '1 message'
        WHEN messages BETWEEN 2 AND 3 THEN '2-3 messages'
        WHEN messages BETWEEN 4 AND 6 THEN '4-6 messages'
        WHEN messages BETWEEN 7 AND 10 THEN '7-10 messages'
        ELSE '11+ messages'
    END AS session_size,
    COUNT(*) AS sessions,
    ROUND(AVG(session_time_seconds)::numeric, 0) AS avg_session_duration_s
FROM session_stats
GROUP BY session_size
ORDER BY MIN(messages);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Daily request volume and outcome breakdown
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
-- 4. Cost and token summary by date, with daily budget utilization
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
    COALESCE(SUM(total_tokens), 0) AS total_tokens,
    ROUND(COALESCE(SUM(cost_eur), 0)::numeric, 2) AS total_cost_eur,
    ROUND(
        COALESCE(SUM(cost_eur), 0)::numeric / NULLIF(:daily_budget, 0) * 100,
        1
    ) AS budget_used_pct
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Response latency by date (successful runs only).
--    time_to_first_token = wait before the answer starts appearing;
--    max_response_duration_s = the slowest single run that day.
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COUNT(*) AS requests,
    ROUND(AVG(duration_seconds)::numeric, 2) AS avg_response_duration_s,
    ROUND(AVG(time_to_first_token)::numeric, 2) AS avg_time_to_first_token_s,
    ROUND(MAX(duration_seconds)::numeric, 2) AS max_response_duration_s
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
  AND response_status = 'success'
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Non-success rate by date, split into genuine errors and budget blocks
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (WHERE response_status = 'error') AS errors,
    COUNT(*) FILTER (WHERE response_status = 'budget_exceeded') AS budget_exceeded,
    ROUND(
        (COUNT(*) FILTER (WHERE response_status != 'success'))::numeric / NULLIF(COUNT(*), 0) * 100,
        1
    ) AS non_success_rate_pct
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY date
ORDER BY date;


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Weekly summary
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    TO_CHAR(DATE_TRUNC('week', date)::date, 'DD-Mon-YYYY') AS week_start,
    COUNT(*) AS total_requests,
    COUNT(DISTINCT anonymous_session_id) AS unique_sessions,
    COALESCE(SUM(total_tokens), 0) AS total_tokens,
    ROUND(COALESCE(SUM(cost_eur), 0)::numeric, 2) AS total_cost_eur,
    ROUND(AVG(duration_seconds)::numeric, 2) AS avg_response_duration_s,
    COUNT(*) FILTER (WHERE response_status != 'success') AS non_success_count
FROM agent_usage_metrics
WHERE date BETWEEN :from_date AND :to_date
GROUP BY DATE_TRUNC('week', date)
ORDER BY DATE_TRUNC('week', date);


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. Unique users and engagement: how many distinct visitors, how often they
--    come back, and what each costs / spends on average.
--    Session time uses last-minus-first message, with the single-message
--    fallback to run duration.
-- ─────────────────────────────────────────────────────────────────────────────
WITH user_session_stats AS (
    SELECT
        anonymous_user_id,
        anonymous_session_id,
        COUNT(*) AS messages,
        SUM(cost_eur) AS session_cost,
        CASE
            WHEN COUNT(*) = 1 THEN COALESCE(MAX(duration_seconds), 0)
            ELSE EXTRACT(EPOCH FROM MAX(created_at) - MIN(created_at))
        END AS session_time_seconds
    FROM agent_usage_metrics
    WHERE date BETWEEN :from_date AND :to_date
      AND anonymous_user_id IS NOT NULL
    GROUP BY anonymous_user_id, anonymous_session_id
)
SELECT
    COUNT(DISTINCT anonymous_user_id) AS unique_users,
    COUNT(DISTINCT anonymous_session_id) AS total_sessions,
    ROUND(
        COUNT(DISTINCT anonymous_session_id)::numeric
        / NULLIF(COUNT(DISTINCT anonymous_user_id), 0),
        2
    ) AS avg_sessions_per_user,
    ROUND(
        SUM(messages)::numeric / NULLIF(COUNT(DISTINCT anonymous_user_id), 0),
        2
    ) AS avg_requests_per_user,
    ROUND(
        SUM(session_cost)::numeric / NULLIF(COUNT(DISTINCT anonymous_user_id), 0),
        2
    ) AS avg_cost_per_user_eur,
    ROUND(
        SUM(session_time_seconds)::numeric / NULLIF(COUNT(DISTINCT anonymous_user_id), 0),
        0
    ) AS avg_time_spent_per_user_s
FROM user_session_stats;


-- ─────────────────────────────────────────────────────────────────────────────
-- 9. New vs returning users per week. A user's first-ever visit is computed
--    over the WHOLE table (not the report range), so users who were first
--    seen before the range are correctly classified as returning.
-- ─────────────────────────────────────────────────────────────────────────────
WITH first_seen AS (
    SELECT
        anonymous_user_id,
        MIN(date) AS first_date
    FROM agent_usage_metrics
    WHERE anonymous_user_id IS NOT NULL
    GROUP BY anonymous_user_id
),
weekly_active AS (
    SELECT DISTINCT
        DATE_TRUNC('week', date)::date AS week_start,
        anonymous_user_id
    FROM agent_usage_metrics
    WHERE date BETWEEN :from_date AND :to_date
      AND anonymous_user_id IS NOT NULL
)
SELECT
    TO_CHAR(w.week_start, 'DD-Mon-YYYY') AS week_start,
    COUNT(*) FILTER (WHERE DATE_TRUNC('week', f.first_date)::date = w.week_start) AS new_users,
    COUNT(*) FILTER (WHERE DATE_TRUNC('week', f.first_date)::date < w.week_start) AS returning_users
FROM weekly_active w
JOIN first_seen f USING (anonymous_user_id)
GROUP BY w.week_start
ORDER BY w.week_start;


-- ─────────────────────────────────────────────────────────────────────────────
-- 10. Per-user aggregate: sessions, requests, tokens, cost, time spent
-- ─────────────────────────────────────────────────────────────────────────────
WITH session_stats AS (
    SELECT
        anonymous_user_id,
        anonymous_session_id,
        COUNT(*) AS messages,
        SUM(total_tokens) AS session_tokens,
        SUM(cost_eur) AS session_cost,
        CASE
            WHEN COUNT(*) = 1 THEN COALESCE(MAX(duration_seconds), 0)
            ELSE EXTRACT(EPOCH FROM MAX(created_at) - MIN(created_at))
        END AS session_time_seconds,
        MIN(date) AS session_date
    FROM agent_usage_metrics
    WHERE date BETWEEN :from_date AND :to_date
      AND anonymous_user_id IS NOT NULL
    GROUP BY anonymous_user_id, anonymous_session_id
)
SELECT
    anonymous_user_id,
    COUNT(DISTINCT anonymous_session_id) AS sessions,
    SUM(messages) AS requests,
    SUM(session_tokens) AS total_tokens,
    ROUND(SUM(session_cost)::numeric, 2) AS total_cost_eur,
    ROUND(SUM(session_time_seconds)::numeric, 0) AS total_time_spent_s,
    TO_CHAR(MIN(session_date), 'DD-Mon-YYYY') AS first_seen,
    TO_CHAR(MAX(session_date), 'DD-Mon-YYYY') AS last_seen
FROM session_stats
GROUP BY anonymous_user_id
ORDER BY requests DESC;
