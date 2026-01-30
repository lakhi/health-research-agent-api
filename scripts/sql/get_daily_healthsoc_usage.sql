-- =============================================================================
-- Get Daily Healthsoc Chatbot Usage
-- =============================================================================
-- 
-- Description:
--   Retrieves the total daily usage and remaining budget for the healthsoc
--   chatbot on a specified date.
--
-- Usage:
--   psql -v target_date="'29-Jan-2026'" -v daily_budget=2.0 -f get_daily_healthsoc_usage.sql
--
--   Or directly in psql:
--   \set target_date '''29-Jan-2026'''
--   \set daily_budget 2.0
--   \i get_daily_healthsoc_usage.sql
--
-- Parameters:
--   :target_date  - Date in 'DD-Mon-YYYY' format (e.g., '29-Jan-2026')
--   :daily_budget - Daily budget in EUR (e.g., 2.0)
--
-- Output columns:
--   date            - The queried date
--   total_input_tokens   - Sum of input tokens used
--   total_output_tokens  - Sum of output tokens used
--   total_cost_eur       - Total cost in EUR
--   remaining_eur        - Remaining budget in EUR
--   budget_exceeded      - Boolean indicating if budget was exceeded
-- =============================================================================

SELECT 
    TO_CHAR(date, 'DD-Mon-YYYY') AS date,
    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
    ROUND(COALESCE(SUM(cost_eur), 0)::numeric, 4) AS total_cost_eur,
    ROUND((:daily_budget - COALESCE(SUM(cost_eur), 0))::numeric, 4) AS remaining_eur,
    CASE 
        WHEN COALESCE(SUM(cost_eur), 0) >= :daily_budget THEN TRUE 
        ELSE FALSE 
    END AS budget_exceeded
FROM daily_healthsoc_chatbot_usage
WHERE date = TO_DATE(:target_date, 'DD-Mon-YYYY')
GROUP BY date;

-- =============================================================================
-- Alternative: Get usage for a date range (last 7 days example)
-- =============================================================================
-- SELECT 
--     TO_CHAR(date, 'DD-Mon-YYYY') AS date,
--     COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
--     COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
--     ROUND(COALESCE(SUM(cost_eur), 0)::numeric, 4) AS total_cost_eur
-- FROM daily_healthsoc_chatbot_usage
-- WHERE date >= CURRENT_DATE - INTERVAL '7 days'
-- GROUP BY date
-- ORDER BY date DESC;
