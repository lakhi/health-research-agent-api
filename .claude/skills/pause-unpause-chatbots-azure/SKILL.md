---
name: pause-unpause-chatbots-azure
description: "Pause or unpause the Azure stacks for the health-research chatbots (hex-gig, vax-study, ssc-psych) — Container Apps scale-to-zero, PostgreSQL stopped, scheduled jobs disabled. Detects each project's current state, asks which to toggle, then acts. Subscriptions: Project - socialeconpsy and Project vaxcommunication."
argument-hint: ""
user-invocable: true
---

# Pause / Unpause Chatbots on Azure

Toggle any combination of the three chatbot stacks between **paused** (Container Apps scaled to
zero, PostgreSQL stopped, scheduled jobs disabled) and **running**.

The skill detects each project's current state first, shows those states in a multi-select, and
toggles only what the user picks — each selected project flips to the opposite of *its own* state,
so pausing one project while unpausing another in the same run is supported.

## Project Registry

| Project | Subscription | RG | API app | UI app | Scheduled job | Database |
|---|---|---|---|---|---|---|
| `hex-gig` | `444c1e5c-ac0d-4420-94ea-d4a5414d20e1` | `healthsociety` | `hex-gig-agent-api` | `hex-gig-agent-ui` | `hex-gig-rss-refresh` | `hex-gig-postgres-db` (**dedicated**) |
| `vax-study` | `44365843-c70c-4844-a430-ad0193819039` | `vax-study` | `marhinovirus-api` | `marhinovirus-infobot` | — | `vax-db` in RG `vax-study` (**shared**) |
| `ssc-psych` | `44365843-c70c-4844-a430-ad0193819039` | `ssc-psych-test` | `ssc-psych-api` | `ssc-psych-chatbot-ui` | — | logical DB `ssc_psych` on the same `vax-db` (**shared**) |

Replica targets — paused is `0/1` for every app; running differs per project:

| Project | Running min/max | Paused min/max |
|---|---|---|
| `hex-gig` | `1` / `3` | `0` / `1` |
| `vax-study` | `1` / `2` | `0` / `1` |
| `ssc-psych` | `1` / `2` | `0` / `1` |

`hex-gig-rss-refresh` cron: `0 12 * * *` when running, `0 0 31 2 *` (Feb 31st — never fires) when paused.

> **`vax-db` is shared by vax-study and ssc-psych.** It must never be stopped while either of them
> is running. See [Shared-database rules](#shared-database-rules) — this is the one piece of logic
> that cannot be decided per project.

## Procedure

### Step 0 — Azure login check

```bash
az account show --output none 2>/dev/null || az login --tenant azure.univie.ac.at
```

Both subscriptions live in the `azure.univie.ac.at` tenant, so one login covers all three projects.
Always pass `--subscription` explicitly on every command rather than relying on the active default.

### Step 1 — Detect current state

Four reads, run in parallel:

```bash
# Container Apps in both subscriptions
az containerapp list --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "[].{name:name,rg:resourceGroup,min:properties.template.scale.minReplicas,max:properties.template.scale.maxReplicas}" -o table

az containerapp list --subscription 44365843-c70c-4844-a430-ad0193819039 \
  --query "[].{name:name,rg:resourceGroup,min:properties.template.scale.minReplicas,max:properties.template.scale.maxReplicas}" -o table

# Both PostgreSQL servers
az postgres flexible-server show --name hex-gig-postgres-db --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 --query "state" -o tsv

az postgres flexible-server show --name vax-db --resource-group vax-study \
  --subscription 44365843-c70c-4844-a430-ad0193819039 --query "state" -o tsv
```

Optionally confirm the hex-gig job cron:

```bash
az containerapp job show --name hex-gig-rss-refresh --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 \
  --query "properties.configuration.scheduleTriggerConfig.cronExpression" -o tsv
```

**Per-project state is read from the API Container App's `minReplicas`** — `0` means paused,
`≥1` means running. Do *not* use PostgreSQL state as the per-project signal: `vax-db` is shared,
so it cannot answer a question about a single project.

**Report drift rather than silently fixing it.** Flag, and mention in the final report, any of:

- API app and UI app of the same project disagreeing (one at `0`, the other at `≥1`)
- a project reading as running while its database is `Stopped` (chat will be broken)
- `hex-gig` running but the RSS cron still set to the disabled expression, or vice versa

Drift does not block the toggle — apply the requested change, then report what was off.

### Step 2 — Ask which projects to toggle

Use **AskUserQuestion** with `multiSelect: true`, one option per project, each label carrying the
detected state and each description naming the concrete resulting action:

```json
{
  "question": "Which chatbot stacks should be toggled?",
  "header": "Projects",
  "multiSelect": true,
  "options": [
    {
      "label": "hex-gig — running",
      "description": "Will PAUSE: agent-api + agent-ui to 0/1, hex-gig-postgres-db stopped, RSS cron disabled."
    },
    {
      "label": "vax-study — running",
      "description": "Will PAUSE: marhinovirus-api + marhinovirus-infobot to 0/1. vax-db stops only if ssc-psych also ends up paused."
    },
    {
      "label": "ssc-psych — paused",
      "description": "Will UNPAUSE: vax-db started first, then ssc-psych-api + ssc-psych-chatbot-ui to 1/2."
    }
  ]
}
```

Build the labels and descriptions from the **actual detected state**, not the example above.
If the user selects nothing, exit without making changes.

### Step 3 — Apply

For each selected project, in its own subscription.

**Pausing:**

```bash
# API and UI to zero
az containerapp update --name <api-app> --resource-group <rg> --subscription <sub> \
  --min-replicas 0 --max-replicas 1
az containerapp update --name <ui-app> --resource-group <rg> --subscription <sub> \
  --min-replicas 0 --max-replicas 1

# hex-gig only — Container Apps Jobs have no native suspend toggle, so overwrite the cron
# with a date that can never occur instead of deleting the schedule.
az containerapp job update --name hex-gig-rss-refresh --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 --cron-expression "0 0 31 2 *"

# hex-gig only — dedicated server, safe to stop whenever hex-gig is paused
az postgres flexible-server stop --name hex-gig-postgres-db --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1
```

**Unpausing** — start the database *first* (it takes ~2 minutes), then scale the apps up:

```bash
az postgres flexible-server start --name <server> --resource-group <db-rg> --subscription <sub>

# hex-gig only — restore the real schedule (there is no `az containerapp job resume`)
az containerapp job update --name hex-gig-rss-refresh --resource-group healthsociety \
  --subscription 444c1e5c-ac0d-4420-94ea-d4a5414d20e1 --cron-expression "0 12 * * *"

az containerapp update --name <api-app> --resource-group <rg> --subscription <sub> \
  --min-replicas 1 --max-replicas <running-max>
az containerapp update --name <ui-app> --resource-group <rg> --subscription <sub> \
  --min-replicas 1 --max-replicas <running-max>
```

Container App updates for different projects are independent and may run in parallel.

### Shared-database rules

`vax-db` is resolved **once per run**, after computing the *projected* post-toggle state of both
tenants — that is, the state each of vax-study and ssc-psych will be in once the selected toggles
are applied, whether or not that project was selected this run.

"Projected paused" therefore covers **both** cases equally, and the skill must not distinguish them:

- the project was **already paused** before this run and was not selected, and
- the project **was selected** this run and is being paused now.

So selecting only ssc-psych to pause, when vax-study is already paused, **stops `vax-db`** — no
second run or extra confirmation needed. Stopping it is automatic whenever the ref-count reaches
zero, by whichever combination of the two.

| Projected vax-study | Projected ssc-psych | Action on `vax-db` |
|---|---|---|
| paused | paused | **Stop** it — automatically, however each tenant reached "paused" |
| running | anything | **Start** it if currently `Stopped`, before scaling apps up |
| anything | running | **Start** it if currently `Stopped`, before scaling apps up |

When the database is deliberately left running because the other tenant is still up, **say so in
the report** — otherwise the user will expect full savings and not get them:

> `vax-db` left running — ssc-psych is still active on it. Pausing vax-study alone saves its
> Container App spend (~€13/month) but not the database (~€14/month).

`hex-gig-postgres-db` is dedicated and needs none of this: stop it whenever hex-gig is paused.

### Step 4 — Verify

Re-run the Step 1 detection reads and confirm each toggled project reached its target. PostgreSQL
takes ~2 minutes to reach `Ready` after a start, so a freshly unpaused server may still report
`Starting` — report that as in-progress rather than as a failure.

### Step 5 — Report

Print a per-project table of the final state (API/UI replicas, database, job cron where relevant),
then:

- what state each project was in and what action was taken
- any drift detected in Step 1
- the `vax-db` decision and its reason, whenever it was left running or shared-stopped
- on unpause: PostgreSQL needs ~2 minutes to become fully `Ready`; the apps will serve once it is
- estimated cost effect, using the measured figures in [Cost Context](#cost-context)

### The re-pause deadline line (mandatory)

Whenever a run leaves **`vax-db` stopped**, the **very last line of the report** must state the date
by which the skill has to be re-run to keep it paused. There is no automation for `vax-db` yet (see
[The 7-Day PostgreSQL Auto-Restart](#the-7-day-postgresql-auto-restart)), so this line is the only
thing standing between a paused stack and silently resumed billing.

Compute the dates from the day the server was stopped:

```bash
echo "auto-restart on/around: $(date -u -v+7d +%Y-%m-%d)"
echo "re-run this skill by:   $(date -u -v+6d +%Y-%m-%d)"
```

Emit it as the final line, visually separated so it is not lost in the report body:

```
⏰ RE-PAUSE DEADLINE — vax-db auto-restarts on or around 2026-08-19.
   Re-run /pause-unpause-chatbots-azure by 2026-08-18 to keep it paused (~€13.72/month at stake).
```

Rules for this line:

- Include it **only** when `vax-db` ends the run `Stopped`. If it was left running because a tenant
  is still active, there is no deadline — say that instead.
- `hex-gig-postgres-db` never needs this line: the `keep-paused-postgres.yml` workflow re-stops it
  automatically every 6 days. Do not imply hex-gig needs manual attention.
- Once `AZURE_CREDENTIALS_VAXCOMMUNICATION` exists, `vax-db` becomes automated too and this line
  should be dropped from the skill.

## Decision Rules

- Never stop `vax-db` while either vax-study or ssc-psych is projected to be running.
- Never act on a PostgreSQL server in `Starting`, `Stopping`, or `Updating` state — skip that
  database, report it, and still apply the Container App changes for the selected projects.
- On unpause, start PostgreSQL before scaling apps up; the apps come up fast and will retry until
  the database answers, but an app that boots first will log connection errors.
- Never silently normalise drift — apply what was asked, report what was off.
- A project that is already in the requested state is a no-op; say so rather than re-issuing the
  update commands.

## Cost Context

All figures are measured from Azure Cost Management, in EUR, via `az rest` against
`Microsoft.CostManagement/query` (the `az costmanagement query` CLI command was removed from the
extension — use the REST API directly).

### hex-gig — `healthsociety` (2026-05-08 → 2026-07-22, 76 days, €159.30)

- **Running**: ~€2.10/day, ~**€63/month**. Container Apps 72% (€115.02), PostgreSQL 21% (€33.62),
  ACR 6% (€9.91), Azure OpenAI <1% (€0.74).
- **Paused**: ~€0.13/day, ~**€4/month** (ACR storage only).
- **Saving**: ~**€59/month (~94%)**.

### vaxcommunication — `vax-study` + `ssc-psych-test` (2026-07-13 → 2026-08-12, 30 days, €54.12)

| Component | €/month | Pausable? |
|---|---|---|
| vax-study Container Apps | 13.04 | ✅ with vax-study |
| ssc-psych Container Apps | 11.77 | ✅ with ssc-psych |
| `vax-db` PostgreSQL | 13.72 | ⚠️ only when **both** are paused |
| Azure OpenAI (Foundry Models) | 8.52 | ✅ usage-based, falls to ~0 when idle |
| ACR (`vaxacr` + `sscpsychacr`) | 7.08 | ❌ storage, always billed |

- **Both paused**: residual ~€7.08/month (ACR only) — a saving of ~**€47/month (~87%)**.
- **vax-study alone paused**: saves ~€13/month of Container Apps plus most Azure OpenAI usage;
  `vax-db` keeps billing because ssc-psych still needs it.
- **ssc-psych alone paused**: saves ~€12/month of Container Apps; `vax-db` keeps billing.

⚠️ **RG totals are not project totals.** `vax-db` and `az-openai-vax-models` are shared but billed
entirely to the `vax-study` resource group, so ssc-psych's true cost is higher than its RG line
suggests and vax-study's is lower.

## The 7-Day PostgreSQL Auto-Restart

Azure force-restarts a stopped Flexible Server after 7 days. The
`.github/workflows/keep-paused-postgres.yml` workflow runs every 6 days and re-stops any server it
finds `Ready` that should be paused, so a stack stays paused indefinitely once this skill has
paused it. Trigger it manually from the GitHub Actions UI only to force an immediate check.

- **`hex-gig-postgres-db`** — fully automated via the `AZURE_CREDENTIALS_SOCIALECONPSY` secret.
- **`vax-db`** — the workflow job exists and is ref-count-aware (it re-stops the server only when
  *both* `marhinovirus-api` and `ssc-psych-api` sit at `minReplicas: 0`), but it is gated on an
  `AZURE_CREDENTIALS_VAXCOMMUNICATION` secret that **does not exist yet** and skips until it does.

  Creating it needs a service principal, which requires `Microsoft.Authorization/roleAssignments/write`
  on the `vaxcommunication` subscription. That permission is currently **not held** — the account has
  Contributor there, but not `User Access Administrator` (which it does hold on `socialeconpsy`,
  which is why hex-gig's automation exists and vax's does not). Until an Azure admin grants it,
  **a paused `vax-db` will silently restart itself after ~7 days** and quietly resume billing.
  Re-run this skill to re-pause it. This is why every run that leaves `vax-db` stopped must end with
  the [re-pause deadline line](#the-re-pause-deadline-line-mandatory).

  Once the permission is granted:

  ```bash
  az ad sp create-for-rbac --name keep-vax-db-paused --role Contributor \
    --scopes /subscriptions/44365843-c70c-4844-a430-ad0193819039/resourceGroups/vax-study/providers/Microsoft.DBforPostgreSQL/flexibleServers/vax-db \
    --sdk-auth > sp.json
  # Reader on the two API apps so the job can evaluate the ref-count
  APP_ID=$(jq -r .clientId sp.json)
  az role assignment create --assignee "$APP_ID" --role Reader \
    --scope /subscriptions/44365843-c70c-4844-a430-ad0193819039/resourceGroups/vax-study/providers/Microsoft.App/containerapps/marhinovirus-api
  az role assignment create --assignee "$APP_ID" --role Reader \
    --scope /subscriptions/44365843-c70c-4844-a430-ad0193819039/resourceGroups/ssc-psych-test/providers/Microsoft.App/containerapps/ssc-psych-api
  gh secret set AZURE_CREDENTIALS_VAXCOMMUNICATION < sp.json && rm -f sp.json
  ```

  `sp.json` holds a client secret — never print it, and delete it as shown.
