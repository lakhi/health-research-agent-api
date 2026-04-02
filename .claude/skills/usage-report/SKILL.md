---
name: usage-report
description: "Run agent usage metrics reporting queries and present a tabular Q&A breakdown with summary & analysis. Reads from the agent_usage_metrics table via the local pgvector DB."
argument-hint: "from=YYYY-MM-DD to=YYYY-MM-DD"
user-invocable: true
---

# Usage Report

Run all 8 queries from `scripts/sql/usage_reports.sql` and present the results as labelled question-answer tables followed by a written summary & analysis.

## Inputs

Both arguments are optional:

- `from` — report start date in `YYYY-MM-DD` format (default: earliest date in the table)
- `to` — report end date in `YYYY-MM-DD` format (default: today in Vienna timezone)

Example invocations:
- `/usage-report` — full available date range
- `/usage-report from=2026-04-01` — from a specific start date to today
- `/usage-report from=2026-03-01 to=2026-03-31` — a specific window

## Procedure

### Step 1 — Read DB credentials

Read `.env` and extract the following variables:

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`

Construct the base psql command:

```bash
PGPASSWORD=<DB_PASSWORD> psql -h <DB_HOST> -p <DB_PORT> -U <DB_USER> -d <DB_NAME>
```

Note: `DB_HOST` in `.env` is the Docker internal hostname (`pgvector`). When connecting from the host machine, use `localhost` instead.

### Step 2 — Resolve date range

If `from` was not supplied, query the table for the earliest date:

```bash
PGPASSWORD=<DB_PASSWORD> psql -h localhost -p <DB_PORT> -U <DB_USER> -d <DB_NAME> \
  -t -c "SELECT MIN(date) FROM agent_usage_metrics;"
```

If `to` was not supplied, use today's date in the `Europe/Vienna` timezone.

If the table is empty (MIN(date) returns NULL), report **"No usage data found in the agent_usage_metrics table."** and stop.

### Step 3 — Run the reporting queries

```bash
PGPASSWORD=<DB_PASSWORD> psql -h localhost -p <DB_PORT> -U <DB_USER> -d <DB_NAME> \
  -v from_date="'<from>'" \
  -v to_date="'<to>'" \
  -f scripts/sql/usage_reports.sql
```

If the connection fails, report the error and the connection parameters used (mask the password as `***`). Do not retry.

### Step 4 — Present results

Present all results in the following structure:

**For each of the 8 queries**, output a section with:
1. A heading stating the question the query answers
2. The query result formatted as a markdown table

Use these headings (in order):

1. **How many unique sessions and total requests were there?**
2. **Which sessions had more than one message, and how long did they last?**
3. **How many requests were made each day, and what was the outcome breakdown?**
4. **How many tokens were consumed and what did it cost each day?**
5. **When during the day is the agent being used? (Vienna time)**
6. **How fast is the agent responding each day?**
7. **What is the error rate each day?**
8. **What does the weekly rollup look like?**

Then write a **Summary & Analysis** section (prose) covering:
- Overall volume and session behaviour (total requests, unique sessions, multi-message session patterns)
- Token consumption and EUR cost (input/output ratio, daily trend)
- Response latency (avg, TTFT, max — and what they suggest about retrieval performance)
- Error/budget_exceeded rate
- Any notable usage patterns (time-of-day, day-over-day trends)

## Decision Rules

- This skill is **read-only** — never modify any files or database records.
- If a query returns zero rows, show an empty table with headers and a note "(no data in range)".
- If `from` is after `to`, report the invalid range and stop.
- Do not open a PR or commit anything.
