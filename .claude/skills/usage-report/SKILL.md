---
name: usage-report
description: "Run agent usage metrics reporting queries and present a tabular Q&A breakdown with summary & analysis. Reads from the agent_usage_metrics table via the local pgvector DB."
argument-hint: "from=YYYY-MM-DD to=YYYY-MM-DD"
user-invocable: true
---

# Usage Report

Run all 8 queries from `scripts/sql/usage_reports.sql` and present the results as labelled question-answer tables followed by a written summary & analysis.

## Inputs

All arguments are optional:

- `from` — report start date in `YYYY-MM-DD` format (default: earliest date in the table)
- `to` — report end date in `YYYY-MM-DD` format (default: today in Vienna timezone)
- `format` — output format: omit for markdown-only, or pass `format=html` to also write a self-contained HTML report file to `reports/`

Example invocations:
- `/usage-report` — full available date range, markdown only
- `/usage-report from=2026-04-01` — from a specific start date to today
- `/usage-report from=2026-03-01 to=2026-03-31` — a specific window
- `/usage-report format=html` — full range, markdown + HTML report written to `reports/`
- `/usage-report from=2026-04-01 format=html` — from a specific start date, markdown + HTML

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

### Step 5 — Generate HTML artifact (only if `format=html` was passed)

Skip this step entirely if `format=html` was not supplied.

**Determine the output filename:**
- Both `from` and `to` supplied (or resolved): `reports/agent-usage-<from>_to_<to>.html`
- Neither supplied (full range): `reports/agent-usage-<to>.html` where `<to>` is today

Create the `reports/` directory if it does not exist:
```bash
mkdir -p reports
```

Write a self-contained HTML file using the Write tool with this structure:

**`<head>`** — Inter font via Google Fonts; all styles in an inline `<style>` block.
Design tokens (match the `/insights` report style):
- Page bg: `#f8fafc`, body text: `#334155`, headings: `#0f172a`
- Card: white background, border `1px solid #e2e8f0`, `border-radius: 8px`, `padding: 24px`
- Header bar bg: `#0f172a` with white text
- Table header bg: `#f1f5f9`; table borders: `#e2e8f0`; striped rows: alternate `#f8fafc`
- Font stack: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif`

**Header section:**
- `<h1>` — "Agent Usage Report"
- Subtitle — date range + "Generated `<YYYY-MM-DD HH:MM>` Vienna time"
- Stat chips row (4 chips): **Total Requests** · **Unique Sessions** · **Total Cost (EUR)** · **Total Tokens**
  Pull values from Q1 (requests, sessions) and the sum of Q4 (cost, tokens) already in context.

**Navigation ToC:** inline anchor links to Q1–Q8 sections and the Summary.

**8 query sections** — one white card per query:
- `<h2 id="q1">` etc. using the same headings as Step 4
- Data as `<table>` with `<thead>` and `<tbody>`
- If a query returned zero rows: render the column headers + a single row with "(no data in range)" spanning all columns

**Summary & Analysis section:**
- `<h2 id="summary">Summary & Analysis</h2>`
- The same prose written in Step 4, wrapped in `<p>` tags inside a white card

**Footer:**
```
Generated by /usage-report skill · health-research-agent-api
```

After writing the file, print in chat:
```
HTML report written to `reports/<filename>.html`
```

---

## Decision Rules

- This skill is **read-only** — it never modifies database records.
- The only file it may write is the HTML report under `reports/` when `format=html` is passed.
- If a query returns zero rows, show an empty table with headers and a note "(no data in range)".
- If `from` is after `to`, report the invalid range and stop.
- HTML generation must not suppress or replace the markdown output — both always appear when `format=html` is used.
- The `reports/` directory is git-ignored and created at runtime; do not commit generated HTML files.
- Do not open a PR or commit anything.
