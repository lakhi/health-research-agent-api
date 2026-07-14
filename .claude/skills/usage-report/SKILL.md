---
name: usage-report
description: "Run agent usage metrics reporting queries and present a tabular Q&A breakdown with summary & analysis. Reads the agent_usage_metrics table of the live HeX-GiG Azure DB by default (target=local for the local pgvector DB)."
argument-hint: "period=weekly|monthly from=YYYY-MM-DD to=YYYY-MM-DD target=live|local format=html"
user-invocable: true
---

# Usage Report

Run all 10 queries from `scripts/sql/usage_reports.sql` and present the results as labelled question-answer tables followed by a written summary & analysis.

## Inputs

All arguments are optional:

- `target` — `live` (default) reads the **live HeX-GiG Azure database**; `local` reads the local pgvector DB
- `period` — `weekly` = the last complete Mon–Sun week; `monthly` = the previous calendar month (both Vienna time)
- `from` / `to` — explicit dates in `YYYY-MM-DD` format; if given they **override** `period` (defaults when neither period nor dates are given: earliest date in the table → today in Vienna)
- `format` — omit for markdown-only, or pass `format=html` to also write a self-contained HTML report file to `reports/`

Example invocations:
- `/usage-report` — live DB, full available date range, markdown only
- `/usage-report period=weekly format=html` — live DB, last complete week, markdown + HTML
- `/usage-report period=monthly format=html` — live DB, previous calendar month, markdown + HTML
- `/usage-report target=local from=2026-03-01 to=2026-03-31` — local DB, specific window

## Procedure

### Step 1 — Resolve DB credentials

#### target=live (default)

The source of truth is the running Container App — **never** read a local `.env` file for live credentials (it is known to drift from what's actually deployed).

1. Check `az account show` succeeds; if not, ask the user to log in (`az login`). Subscription: `444c1e5c-ac0d-4420-94ea-d4a5414d20e1` ("Project - socialeconpsy").
2. Read the live app's env config:
   ```bash
   az containerapp show -n hex-gig-agent-api -g healthsociety \
     --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
     --query "properties.template.containers[0].env" -o json
   ```
   Extract `DB_HOST`, `DB_PORT`, `DB_USER`, the database name (`DB_DATABASE` or `DB_NAME`), the password (`DB_PASS` or `DB_PASSWORD`), and `DAILY_BUDGET_EUR`. Any value given as a `secretRef` must be resolved via:
   ```bash
   az containerapp secret list -n hex-gig-agent-api -g healthsociety \
     --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 --show-values -o json
   ```
3. Check the PostgreSQL server state:
   ```bash
   az postgres flexible-server show -n hex-gig-postgres-db -g healthsociety \
     --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 --query "state" -o tsv
   ```
   If it is not `Ready` (e.g. `Stopped` because the stack is paused): **stop and ask the user** whether to start it (suggest `/hex-gig-azure-toggle`). Never start it silently.
4. Base psql command (Azure requires SSL):
   ```bash
   PGPASSWORD=<password> psql "host=<DB_HOST> port=<DB_PORT> user=<DB_USER> dbname=<dbname> sslmode=require"
   ```
5. If the connection **times out**, the server firewall probably doesn't allow the current IP. Ask the user before adding a rule:
   ```bash
   az postgres flexible-server firewall-rule create -g healthsociety -n hex-gig-postgres-db \
     --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
     --rule-name usage-report-$(date +%Y%m%d) \
     --start-ip-address <current public IP> --end-ip-address <current public IP>
   ```

#### target=local

Read `.env` and extract `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DAILY_BUDGET_EUR`.

Note: `DB_HOST` in `.env` is the Docker internal hostname (`pgvector`). When connecting from the host machine, use `localhost` instead:

```bash
PGPASSWORD=<DB_PASSWORD> psql -h localhost -p <DB_PORT> -U <DB_USER> -d <DB_NAME>
```

### Step 2 — Resolve date range

Priority: explicit `from`/`to` > `period` > full range. All date arithmetic in `Europe/Vienna`.

- `period=weekly` → the last **complete** Mon–Sun week (e.g. on Thu 02-Jul-2026: from `2026-06-22` to `2026-06-28`)
- `period=monthly` → the previous calendar month (e.g. in Jul 2026: from `2026-06-01` to `2026-06-30`)
- No period and no `from` → query the table for the earliest date:
  ```bash
  <base psql> -t -c "SELECT MIN(date) FROM agent_usage_metrics;"
  ```
- No period and no `to` → today in Vienna.

If the table is empty (MIN(date) returns NULL), report **"No usage data found in the agent_usage_metrics table."** and stop.

### Step 3 — Run the reporting queries

```bash
<base psql> \
  -v from_date="'<from>'" \
  -v to_date="'<to>'" \
  -v daily_budget=<DAILY_BUDGET_EUR> \
  -f scripts/sql/usage_reports.sql
```

If `DAILY_BUDGET_EUR` could not be resolved, pass `-v daily_budget=NULL` (the budget column will render empty rather than wrong).

If the connection fails, report the error and the connection parameters used (mask the password as `***`). Do not retry (except the one firewall-rule path in Step 1).

### Step 4 — Present results

Present all results in the following structure:

**For each of the 10 queries**, output a section with:
1. A heading stating the question the query answers
2. The query result formatted as a markdown table

Use these headings (in order):

1. **How many unique sessions and total requests were there?**
2. **How many sessions had more than one message, and how long did they last on average?**
3. **How many requests were made each day, and what was the outcome breakdown?**
4. **How many tokens were consumed, what did it cost each day, and how much of the daily budget did it use?**
5. **How fast is the agent responding each day?**
   Add one explanatory line under the heading: *avg_time_to_first_token_s is how long users wait before the answer starts appearing; max_response_duration_s is the slowest single run that day. Successful runs only.*
6. **How often do requests fail, and why?**
   Add one explanatory line: *errors are failed agent runs; budget_exceeded are requests refused because the daily EUR budget was already spent.*
7. **What does the weekly rollup look like?**
8. **How many unique users were there, and how engaged were they?**
9. **How many users each week were new vs returning?**
10. **What does each individual user's usage look like?**

Under sections 8–10, include this footnote once (also required in the HTML):
> *A "user" is one anonymous browser profile (a random UUID in the browser's localStorage) — the same person on two devices counts twice, and clearing browser data creates a new user. Requests recorded before user tracking existed have no user id and are excluded here.*

Then write a **Summary & Analysis** section (prose) covering:
- Overall volume and session behaviour (total requests, unique sessions, session-size distribution)
- Per-user engagement — unique users, sessions per user, average time spent per user, new vs returning trend
- Token consumption, EUR cost, and daily budget utilization
- Response latency (avg, TTFT, max — and what they suggest about retrieval performance)
- Error / budget_exceeded rates

**All dates and timestamps in the rendered output (markdown and HTML) use `DD-MMM-YYYY` / `DD-MMM-YYYY HH:MM` format (e.g. `02-Jul-2026 14:30`) — never ISO.**

### Step 5 — Generate HTML artifact (only if `format=html` was passed)

Skip this step entirely if `format=html` was not supplied.

**Determine the output filename** (filenames keep ISO dates for sortability):
- `period=weekly`: `reports/agent-usage-weekly-<from>_to_<to>.html`
- `period=monthly`: `reports/agent-usage-monthly-<YYYY-MM>.html`
- Explicit `from`/`to`: `reports/agent-usage-<from>_to_<to>.html`
- Full range: `reports/agent-usage-<to>.html` where `<to>` is today

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
- Subtitle — data source + period + date range + generation time, all dates in `DD-MMM-YYYY`, e.g.:
  `Live · hex-gig  ·  Weekly report: 22-Jun-2026 → 28-Jun-2026  ·  Generated 02-Jul-2026 14:30 Vienna time`
  (use `Local` instead of `Live · hex-gig` for target=local; omit the period label when no period was given)
- Stat chips row (5 chips): **Total Requests** · **Unique Sessions** · **Unique Users** · **Total Cost (EUR)** (2 decimal places) · **Total Tokens**
  Pull values from Q1 (requests, sessions), Q8 (users), and the sum of Q4 (cost, tokens) already in context.

**Navigation ToC:** inline anchor links to Q1–Q10 sections and the Summary.

**10 query sections** — one white card per query:
- `<h2 id="q1">` etc. using the same headings as Step 4
- The explanatory lines for Q5/Q6 and the user-definition footnote for Q8–Q10 as small muted text under the heading
- Data as `<table>` with `<thead>` and `<tbody>`
- If a query returned zero rows: render the column headers + a single row with "(no data in range)" spanning all columns

**Summary & Analysis section:**
- `<h2 id="summary">Summary & Analysis</h2>`
- The same prose written in Step 4, wrapped in `<p>` tags inside a white card

**Footer** (date in `DD-MMM-YYYY`):
```
Generated by /usage-report skill · health-research-agent-api · <DD-MMM-YYYY>
```

After writing the file, print in chat:
```
HTML report written to `reports/<filename>.html`
```

---

## Decision Rules

- This skill is **read-only** against the database — it never modifies records.
- The only infra change it may ever make is adding a PostgreSQL firewall rule for the current IP, and only after the user agrees.
- Never start a stopped Azure PostgreSQL server without asking the user first.
- Never read a local `.env` file for live credentials — always the Container App config.
- The only file it may write is the HTML report under `reports/` when `format=html` is passed.
- If a query returns zero rows, show an empty table with headers and a note "(no data in range)".
- If `from` is after `to`, report the invalid range and stop.
- HTML generation must not suppress or replace the markdown output — both always appear when `format=html` is used.
- The `reports/` directory is git-ignored and created at runtime; do not commit generated HTML files.
- Do not open a PR or commit anything.
