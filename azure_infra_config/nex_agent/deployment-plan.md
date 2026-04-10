# NEX Agent API — Azure Deployment Plan

Fresh deployment from scratch. Resource group: `healthsociety` (Sweden Central).
Existing in RG: `az-openai-healthsociety` (not used for NEX).

---

## Phase 1 — Provision Infrastructure (Azure Portal, in order)

### 1a. Container Registry — `nex-acr.bicep`
Deploy via Azure Portal ("Deploy a custom template").

> ⚠️ After deployment: Portal → ACR (`nexacr`) → Access keys → **enable admin user**.
> The Bicep sets `adminUserEnabled: false`, but GitHub Actions needs username/password credentials.

### 1b. PostgreSQL Flexible Server — `nex-postgres-db.bicep`
Deploy via Azure Portal.

> ⚠️ The Bicep hardcodes IP `77.80.3.180` (MacBook Pro) for the DB firewall rule.
> If your current IP differs, add a new firewall rule manually after deployment.

### 1c. Azure OpenAI — `az-openai-nex.bicep`
Deploy via Azure Portal. Creates:
- `az-openai-nex` resource
- Model deployments: `gpt-41-nex` (gpt-4.1) and `embedding-large-nex` (text-embedding-3-large)
- Content filter: `nex-content-filter` (blocking, medium severity)

### 1d. Container App Environment — no Bicep, create manually
`nex-agent-api.bicep` depends on `nex-apps-env` existing. Create it first:

```sh
az containerapp env create \
  --name nex-apps-env \
  --resource-group healthsociety \
  --location swedencentral
```

Or via Portal: Create a resource → Container App Environment → name `nex-apps-env`, region Sweden Central.

### 1e. Container App — `nex-agent-api.bicep`
Deploy only after `nex-apps-env` exists.

---

## Phase 2 — Post-Provisioning Setup

### 2a. Initialize PostgreSQL
Run the SQL migration files from the repo root:

```sh
PGPASSWORD='<db-password>' psql \
  -h nex-postgres-db.postgres.database.azure.com \
  -U postgres -d postgres \
  -f scripts/sql/create_daily_agent_usage.sql

PGPASSWORD='<db-password>' psql \
  -h nex-postgres-db.postgres.database.azure.com \
  -U postgres -d postgres \
  -f scripts/sql/create_agent_usage_metrics.sql
```

This creates:
- `daily_agent_usage` — daily token/cost totals for budget enforcement
- `agent_usage_metrics` — per-request anonymous metrics for usage reporting

> Agno session tables are auto-created on first request — no manual SQL needed for those.

### 2b. Container App Secrets
Portal → `nex-agent-api` → Secrets → add:

| Secret name | Source |
|---|---|
| `agno-api-key` | Your Agno account |
| `azure-openai-api-key` | `az-openai-nex` → Keys & Endpoints |
| `azure-embedder-openai-api-key` | Same key as above |
| `db-password` | Password set during PostgreSQL provisioning |

### 2c. Container App Environment Variables
Portal → `nex-agent-api` → Configuration → Environment variables:

| Variable | Value |
|---|---|
| `PROJECT_NAME` | `nex` |
| `DAILY_BUDGET_EUR` | e.g. `2.0` |
| `MODEL_PRICING_INPUT_EUR` | current gpt-4.1 input rate (EUR per 1M tokens) |
| `MODEL_PRICING_OUTPUT_EUR` | current gpt-4.1 output rate (EUR per 1M tokens) |
| `UCLOUD_SHARE_TOKEN` | uCloud share token (for research PDF downloads) |

---

## Phase 3 — Build & Push Docker Image

### 3a. GitHub Actions Secrets
Repo → Settings → Secrets → Actions → add:

| Secret | Value |
|---|---|
| `ACR_LOGIN_SERVER` | `nexacr.azurecr.io` |
| `ACR_USERNAME` | From ACR → Access keys |
| `ACR_PASSWORD` | From ACR → Access keys |

### 3b. Pin Linux-Compatible Requirements
```sh
./scripts/generate_requirements.sh linux-upgrade
```
Commit any changes to `requirements-linux.txt`.

### 3c. Trigger Build
GitHub → Actions → `build-and-push.yml` → **Run workflow** (manual dispatch).

Pushes two tags to ACR:
- `nexacr.azurecr.io/nex-agent-api:latest`
- `nexacr.azurecr.io/nex-agent-api:<git-sha>`

---

## Phase 4 — Deploy & Verify

### 4a. Deploy with Specific Image Tag
```sh
az containerapp update \
  --name nex-agent-api \
  --resource-group healthsociety \
  --image nexacr.azurecr.io/nex-agent-api:<git-sha> \
  --set-env-vars PROJECT_NAME=nex \
  --revision-suffix "$(date +%d | tr -d '\n')$(date +%b | tr '[:upper:]' '[:lower:]')"
```

### 4b. Check Revision Health
```sh
az containerapp revision list \
  --name nex-agent-api \
  --resource-group healthsociety \
  --query "[0].{revisionName:name,provisioningState:properties.provisioningState,healthState:properties.healthState,runningState:properties.runningState,replicas:properties.replicas}" \
  --output table
```
Expected: `provisioningState=Provisioned`, `healthState=Healthy`, `runningState=Running`

### 4c. Deactivate Old Revisions (if any)
```sh
az containerapp revision deactivate \
  --name nex-agent-api \
  --resource-group healthsociety \
  --revision <old-revision-name>
```
