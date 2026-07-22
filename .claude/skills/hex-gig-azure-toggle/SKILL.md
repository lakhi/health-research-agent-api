---
name: hex-gig-azure-toggle
description: "Toggle the HeX-GiG stack on Azure between paused (scale-to-zero + PostgreSQL stopped) and running (PostgreSQL started + Container Apps scaled up). Auto-detects current state and acts accordingly. Subscription: Project - socialeconpsy."
argument-hint: ""
user-invocable: true
---

# HeX-GiG Azure Toggle

Toggle the HeX-GiG stack in the `healthsociety` resource group (subscription `444c1e5c-ac0d-4420-94ea-d4a5414d20e1`) between paused and running states. Auto-detects the current state and performs the opposite action.

## Resources Managed

| Resource | Paused | Running |
|---|---|---|
| `hex-gig-postgres-db` (PostgreSQL Flexible Server) | Stopped | Ready |
| `hex-gig-agent-api` (Container App) | minReplicas=0, maxReplicas=1 | minReplicas=1, maxReplicas=3 |
| `hex-gig-agent-ui` (Container App) | minReplicas=0, maxReplicas=1 | minReplicas=1, maxReplicas=3 |
| `hex-gig-rss-refresh` (Container Apps Job) | cron disabled (`0 0 31 2 *`, never fires) | cron `0 12 * * *` (daily 12:00 UTC) |

## Procedure

### Step 1 — Detect current state

Query PostgreSQL state as the source of truth:

```bash
az postgres flexible-server show \
  --name hex-gig-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "state" -o tsv
```

Interpret the result:
- `Ready` → stack is **running** → proceed to **Pause**
- `Stopped` → stack is **paused** → proceed to **Unpause**
- `Starting` or `Stopping` → stack is mid-transition → **stop**, report the current state, and ask the user to retry once the transition completes

### Step 2a — Pause (if state was `Ready`)

Run all four commands in parallel:

```bash
az containerapp update \
  --name hex-gig-agent-api \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 0 --max-replicas 1

az containerapp update \
  --name hex-gig-agent-ui \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 0 --max-replicas 1

az postgres flexible-server stop \
  --name hex-gig-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1

# Disable the RSS-refresh job so it doesn't fire against a stopped DB while paused.
# Container Apps Jobs have no native suspend toggle — overwrite the cron with a date
# that can never occur (Feb 31st) instead. Restore the real cron on unpause.
az containerapp job update \
  --name hex-gig-rss-refresh \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --cron-expression "0 0 31 2 *"
```

### Step 2b — Unpause (if state was `Stopped`)

Start PostgreSQL first (it takes ~2 min), then scale Container Apps up:

```bash
az postgres flexible-server start \
  --name hex-gig-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1

# Restore the real cron (there is no `az containerapp job resume` command — jobs have
# no native suspend/resume toggle, so pausing/unpausing means swapping the cron expression)
az containerapp job update \
  --name hex-gig-rss-refresh \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --cron-expression "0 12 * * *"

az containerapp update \
  --name hex-gig-agent-api \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 1 --max-replicas 3

az containerapp update \
  --name hex-gig-agent-ui \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 1 --max-replicas 3
```

### Step 3 — Verify

Re-query PostgreSQL state and Container Apps replica config to confirm the transition completed:

```bash
az postgres flexible-server show \
  --name hex-gig-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "state" -o tsv

az containerapp show --name hex-gig-agent-api --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "{minReplicas:properties.template.scale.minReplicas}" -o tsv

az containerapp job show --name hex-gig-rss-refresh --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "properties.configuration.scheduleTriggerConfig.cronExpression" -o tsv
  # expect "0 0 31 2 *" when paused, "0 12 * * *" when running
```

### Step 4 — Report

Report clearly:
- What state was detected
- What action was taken
- Final confirmed state of PostgreSQL, both Container Apps, and the `hex-gig-rss-refresh` job
- If unpausing: remind that PostgreSQL takes ~2 minutes to become fully `Ready` and Container Apps will be live once it does

## Decision Rules

- Never run a pause or unpause if PostgreSQL is in `Starting` or `Stopping` state — report and stop.
- If PostgreSQL state is unexpected (e.g. `Updating`), report it and stop without making changes.
- On unpause, scale Container Apps and start PostgreSQL concurrently (Container Apps scale quickly; they will connect to DB once it's ready).

## Cost Context

Measured from actual Azure Cost Management data for the `healthsociety` RG, 2026-05-08 (when the stack was first deployed) through 2026-07-22 — 76 days, €159.30 total. Query via `az rest` against `Microsoft.CostManagement/query` (the `az costmanagement query` CLI command has been removed from the extension; use the REST API directly).

- **Running**: ~€2.10/day, ~**€63/month**. Breakdown: Container Apps 72% (€115.02), PostgreSQL 21% (€33.62), ACR 6% (€9.91), Azure OpenAI usage <1% (€0.74).
- **Paused**: ~€0.13/day, ~**€4/month** (ACR storage only — Container Apps and PostgreSQL compute drop to ~€0 when scaled to zero / stopped).
- **Savings from pausing**: ~€1.97/day, ~**€59/month (~94% reduction)**.
- ⚠️ Azure auto-restarts stopped PostgreSQL Flexible Servers after 7 days. This is handled automatically: the `pause-hex-gig-postgres` GitHub Actions workflow (`.github/workflows/pause-hex-gig-postgres.yml`) now runs on a `schedule` trigger every 6 days and re-stops the DB if it finds it `Ready`. No manual action needed — it will keep the DB paused indefinitely once this skill has paused the stack. Trigger it manually from the GitHub Actions UI only if you want to force an immediate check.
