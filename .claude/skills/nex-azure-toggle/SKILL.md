---
name: nex-azure-toggle
description: "Toggle the NEX stack on Azure between paused (scale-to-zero + PostgreSQL stopped) and running (PostgreSQL started + Container Apps scaled up). Auto-detects current state and acts accordingly. Subscription: Project - socialeconpsy."
argument-hint: ""
user-invocable: true
---

# NEX Azure Toggle

Toggle the NEX stack in the `healthsociety` resource group (subscription `444c1e5c-ac0d-4420-94ea-d4a5414d20e1`) between paused and running states. Auto-detects the current state and performs the opposite action.

## Resources Managed

| Resource | Paused | Running |
|---|---|---|
| `nex-postgres-db` (PostgreSQL Flexible Server) | Stopped | Ready |
| `nex-agent-api` (Container App) | minReplicas=0, maxReplicas=1 | minReplicas=1, maxReplicas=2 |
| `nex-agent-ui` (Container App) | minReplicas=0, maxReplicas=1 | minReplicas=1, maxReplicas=3 |

## Procedure

### Step 1 — Detect current state

Query PostgreSQL state as the source of truth:

```bash
az postgres flexible-server show \
  --name nex-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "state" -o tsv
```

Interpret the result:
- `Ready` → stack is **running** → proceed to **Pause**
- `Stopped` → stack is **paused** → proceed to **Unpause**
- `Starting` or `Stopping` → stack is mid-transition → **stop**, report the current state, and ask the user to retry once the transition completes

### Step 2a — Pause (if state was `Ready`)

Run all three commands. Container Apps can run in parallel with the PostgreSQL stop:

```bash
az containerapp update \
  --name nex-agent-api \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 0 --max-replicas 1

az containerapp update \
  --name nex-agent-ui \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 0 --max-replicas 1

az postgres flexible-server stop \
  --name nex-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1
```

### Step 2b — Unpause (if state was `Stopped`)

Start PostgreSQL first (it takes ~2 min), then scale Container Apps up:

```bash
az postgres flexible-server start \
  --name nex-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1

az containerapp update \
  --name nex-agent-api \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 1 --max-replicas 2

az containerapp update \
  --name nex-agent-ui \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --min-replicas 1 --max-replicas 3
```

### Step 3 — Verify

Re-query PostgreSQL state and Container Apps replica config to confirm the transition completed:

```bash
az postgres flexible-server show \
  --name nex-postgres-db \
  --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "state" -o tsv

az containerapp show --name nex-agent-api --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "{minReplicas:properties.template.scale.minReplicas}" -o tsv
```

### Step 4 — Report

Report clearly:
- What state was detected
- What action was taken
- Final confirmed state of PostgreSQL and both Container Apps
- If unpausing: remind that PostgreSQL takes ~2 minutes to become fully `Ready` and Container Apps will be live once it does

## Decision Rules

- Never run a pause or unpause if PostgreSQL is in `Starting` or `Stopping` state — report and stop.
- If PostgreSQL state is unexpected (e.g. `Updating`), report it and stop without making changes.
- On unpause, scale Container Apps and start PostgreSQL concurrently (Container Apps scale quickly; they will connect to DB once it's ready).

## Cost Context

- **Paused**: ~$9/month (ACR Basic + storage only)
- **Running**: ~$144/month
- ⚠️ Azure auto-restarts stopped PostgreSQL Flexible Servers after 7 days. If this happens, run `/nex-azure-toggle` to re-pause, or trigger the `pause-nex-postgres` GitHub Actions workflow manually.
