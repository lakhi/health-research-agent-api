---
name: deploy-new-project-to-azure
description: "Interactive step-by-step deployment of a new health-research project (API + UI) to a fresh Azure resource group, based on the VAX-Study Sweden Central setup. Asks which services to deploy, checks what already exists, and either hands the user the commands or runs them itself per phase."
argument-hint: ""
user-invocable: true
---

# Deploy New Project to Azure

Bootstrap a new health-research project (API + optional UI) into a fresh Azure resource group, mirroring the VAX-Study Sweden Central deployment.

The skill is **interactive and per-phase**: it asks which services are required, checks what already exists in the target RG, and either prints the `az` commands for the user to run or executes them itself (with confirmation between phases).

## Inputs

No arguments required — everything is collected interactively in Phase 0.

## Procedure

### Phase 0 — Gather target

Use **AskUserQuestion** in a single batch to collect the deployment target. Propose `Sweden Central` as the default region and the `vax`-style naming convention for resource names (`<slug>acr`, `<slug>-env`, `<slug>-db`, `<slug>-logs`, `<api-name>`, `<ui-name>`).

Required inputs:

1. Subscription ID or name.
2. Resource group name.
3. Azure region (default: `Sweden Central`).
4. Project slug (e.g., `vax`, `nex`, `ssc-psych`).
5. Tag trio: `Kostenstelle`, `Umgebung`, `Verantwortliche*r`.
6. API container app name (default: `<slug>-api`).
7. UI container app name (optional — empty means skip UI).

Then ask the **deployment mode** question:

```json
{
  "question": "How should this deployment run?",
  "header": "Mode",
  "options": [
    {"label": "I'll run the commands myself", "description": "Claude prints each az command and you paste/run it locally. Recommended if you want full control."},
    {"label": "Claude runs it for me", "description": "Claude executes each phase via Bash after you confirm. Will prompt you to run `az login --tenant azure.univie.ac.at && az account set --subscription <id>` first."}
  ]
}
```

Then ask the **components** question (multiSelect, all four pre-selected):

```json
{
  "question": "Which components should be deployed/checked?",
  "header": "Components",
  "multiSelect": true,
  "options": [
    {"label": "ACR", "description": "Container Registry (<slug>acr). Pre-requisite for everything else."},
    {"label": "Log Analytics + Container Apps Environment", "description": "<slug>-logs + <slug>-env. Shared env for API and UI container apps."},
    {"label": "Postgres Flex (pgvector)", "description": "<slug>-db Burstable B1ms with azure.extensions=vector. Skip if no Agno RAG / sessions needed."},
    {"label": "API + UI container apps", "description": "The full agent stack. UI is optional based on Phase 0 inputs."}
  ]
}
```

If the user chose **"Claude runs it for me"**, the very next action is to ask them to run:

```sh
az login --tenant azure.univie.ac.at && az account set --subscription <subscription>
```

Wait for confirmation that they're signed in before any `az` calls.

### Phase 1 — Pre-flight existence check

For each ticked component, run the existence check (in `Claude runs` mode) or print it (in `user runs` mode):

| Component | Check command | If exists, capture |
|---|---|---|
| ACR | `az acr show -g <rg> -n <slug>acr` | `loginServer`; then `az acr credential show -g <rg> -n <slug>acr` for admin user/password |
| Env | `az containerapp env show -g <rg> -n <slug>-env` | `id`, `properties.defaultDomain` |
| Postgres | `az postgres flexible-server show -g <rg> -n <slug>-db` | FQDN; verify `azure.extensions=vector` via `az postgres flexible-server parameter show --server-name <slug>-db -g <rg> --name azure.extensions` |
| API/UI app | `az containerapp show -g <rg> -n <name>` | `properties.configuration.ingress.fqdn` |

For each component that **already exists**, mark it as "reuse" and stash its outputs as inputs for later phases. Skip its create step in Phase 3.

Also sanity-check the Azure OpenAI resource expected to live in the RG (e.g., `az-openai-<slug>-models`):

```sh
az cognitiveservices account deployment list -g <rg> -n az-openai-<slug>-models -o table
```

If the GPT or embedding model deployments the API expects are missing, **stop** and tell the user to create them before continuing.

Display a summary table of "exists / will create" for the ticked components, then proceed.

### Phase 2 — Copy the Bicep template folder

If at least one component needs creation, copy `azure_infra_config/vax_chatbot/` → `azure_infra_config/<slug>_chatbot/` and rewrite resource names. Files to substitute:

- `<slug>-acr.bicep` — ACR name, location, tags
- `<slug>-env.bicep` — Log Analytics + Env names, location, tags
- `<slug>-postgres-db.bicep` — server name, region, tags, pgvector extension, Azure-services firewall rule
- `<slug>-postgres-db.bicepparam` — `administratorLoginPassword` (prompt user; `.bicepparam` is gitignored)
- `<slug>-api.bicep` — Container App name, image (`<slug>acr.azurecr.io/health-research-api:latest`), DB FQDN, registries block (admin-credential ACR auth — see existing `vax-api.bicep`)
- `<slug>-api.bicepparam` — five `@secure` params: `dbPassword`, `agnoApiKey`, `azureOpenAiApiKey`, `azureEmbedderOpenAiApiKey`, `acrPassword`

For the UI side (if requested), in the sibling `agent-ui` repo:

- Copy `infrastructure/vax-ui.bicep` (already credential-based) and reuse it, or create `<slug>-ui.bicep` if a tweak is needed.
- Copy `infrastructure/vax-study-chatbot.bicepparam` → `<slug>-chatbot.bicepparam`.
- Plan an edit to `src/config/projects.tsx` adding the new project's `apiEndpoint` (gets filled in after Phase 3).

Also plan a new `api/project_configs/<slug>_config.py` modelled on `vax_study_config.py` (or update the existing one if this is a redeploy).

**Confirm with the user before writing any of these files.** Show the substitution list.

### Phase 3 — Deploy components in dependency order

For each component flagged "create" in Phase 1, in this strict order — **ACR → Env → DB → API → UI** — present the deploy command and confirm *this phase* before running (or just print the command in user-runs mode):

```sh
RG=<rg>
az deployment group create --resource-group $RG \
  --template-file azure_infra_config/<slug>_chatbot/<slug>-acr.bicep \
  --mode Incremental
# repeat for env / db / api with --parameters azure_infra_config/<slug>_chatbot/<file>.bicepparam where applicable
```

After each successful deploy, refresh the captured outputs from Phase 1 and feed them into the next phase's parameters:

| Output | Consumed by |
|---|---|
| ACR `loginServer` + admin creds | API `bicepparam` (`acrPassword`), UI `bicepparam` (`acrPassword`, `containerRegistryServer`) |
| Env `id` | API `bicep` `managedEnvironmentId`, UI `bicepparam` `managedEnvironmentId` |
| Postgres FQDN | API `bicep` `DB_HOST` env var |
| API FQDN | UI `bicepparam` `apiEndpoint`, `agent-ui/src/config/projects.tsx` |
| UI FQDN | API `cors_origins` in `api/project_configs/<slug>_config.py` (Phase 6) |

### Phase 4 — Build & push the API image

In **user-runs** mode, instruct the user to:

1. In the `health-research-agent-api` GitHub repo settings → Secrets, set `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD`, `PROJECT_NAME` to the new ACR's values.
2. Run `gh workflow run "Build and Push to Azure Container Registry" --ref main`.
3. Wait for the run to go green (`gh run watch`).

In **Claude-runs** mode, do the `gh workflow run` after confirming the secrets are in place (Claude can't touch GitHub secrets).

### Phase 5 — Deploy the UI (optional)

If a UI app was requested:

1. Confirm the `agent-ui` repo has the new project's secrets: `<SLUG>_ACR_LOGIN_SERVER`, `<SLUG>_ACR_USERNAME`, `<SLUG>_ACR_PASSWORD`. (User must add these in GitHub UI.)
2. Trigger `gh workflow run "Deploy <ProjectName> Chatbot"` in the `agent-ui` repo (or instruct user to).
3. Capture the UI FQDN once the workflow goes green.

### Phase 6 — CORS wiring (critical)

This is the round-trip that most often gets forgotten when this is done by hand:

1. Edit `api/project_configs/<slug>_config.py → cors_origins()` to include `https://<ui-fqdn>`.
2. Commit + push to `main` (or instruct user to).
3. Re-trigger the API build workflow so a new image bakes in the CORS update.
4. After the build is green, force the running container app to pick up the new image:

```sh
az containerapp update \
  --name <api-name> --resource-group <rg> \
  --image <slug>acr.azurecr.io/health-research-api:latest \
  --revision-suffix "$(date +%d)-$(date +%b | tr '[:upper:]' '[:lower:]')-$((RANDOM % 10))"
```

### Phase 7 — Smoke test & report

1. Tail logs and watch for `Application startup complete.`:

```sh
az containerapp logs show -g <rg> -n <api-name> --tail 200 --follow
```

2. Open `https://<ui-fqdn>` in a browser, submit a representative question, confirm a cited answer comes back.
3. Print a final summary table:

```
Subscription:   <id>
Resource Group: <rg>
Region:         <region>
ACR:            <slug>acr.azurecr.io
Env:            <slug>-env (defaultDomain: ...)
Postgres:       <slug>-db.postgres.database.azure.com
API:            https://<api-fqdn>
UI:             https://<ui-fqdn>

Pending follow-ups:
  - decommission old RG (if applicable)
  - rotate any temporarily exposed secrets
```

## Notes & gotchas (from the VAX deployment)

- **Cross-region moves are not supported** for Container Apps, Container Apps Env, Postgres Flex, or ACR. Always create fresh in the new region.
- **Postgres server names are globally unique.** If `<slug>-db` is taken, prompt the user for an alternative before deploying.
- **`AcrPull` role assignment requires Owner / UAA**, which we don't have under Contributor-only perms. Always use **admin-credential ACR auth** in the API and UI container apps (already the pattern in the VAX `bicep` files).
- **AZURE_CREDENTIALS service principal also requires admin perms.** Don't add an Azure-login step to the GitHub workflows — keep CI to build+push only and run `az deployment group create` + `az containerapp update` locally.
- **NEXT_PUBLIC_* env vars in the UI are baked at Docker build time.** A change to `apiEndpoint` requires a rebuild + redeploy of the UI image, not just a `containerapp update`.
- **Hardcoded tenant for university work:** `az login --tenant azure.univie.ac.at`.
