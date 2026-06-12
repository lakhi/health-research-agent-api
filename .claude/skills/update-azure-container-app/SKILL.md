---
name: update-azure-container-app
description: "Update the live Azure Container App for a selected project (hex-gig, vax-study, ssc-psych) with the latest code from the GitHub repo main branch. Triggers a GH Actions build, waits for it to go green, then forces the Container App to pull the new image."
argument-hint: ""
user-invocable: true
---

# Update Azure Container App

Build the latest code from `main`, push it to ACR, and force the live Azure Container App to pull the new image — all in one command.

Claude executes all steps directly. Azure login is handled automatically if not already signed in.

## Procedure

### Step 1 — Select project

Use **AskUserQuestion**:

```json
{
  "question": "Which project's Azure Container App should be updated?",
  "header": "Project",
  "multiSelect": false,
  "options": [
    {
      "label": "hex-gig",
      "description": "Builds hex-gig-agent-api → pushes to hexgigacr → updates hex-gig-agent-api in healthsociety RG"
    },
    {
      "label": "vax-study",
      "description": "Builds health-research-api → pushes to vaxacr → updates marhinovirus-api in vax-study RG"
    },
    {
      "label": "ssc-psych",
      "description": "SSC Psychologie chatbot"
    }
  ]
}
```

If the user selects **ssc-psych**: inform them that SSC-Psych has not yet been deployed to Azure — no Container App or ACR exists for it yet. Exit the skill gracefully (no further steps).

### Step 2 — Azure login check

Check whether the CLI is already authenticated:

```sh
az account show --output none 2>/dev/null
```

If that exits with a non-zero code (not logged in), trigger an interactive login:

```sh
az login --tenant azure.univie.ac.at
```

Then set the correct subscription for the chosen project:

| Project   | Subscription ID                        |
|-----------|----------------------------------------|
| hex-gig   | `444c1e5c-ac0d-4420-94ea-d4a5414d20e1` |
| vax-study | `44365843-c70c-4844-a430-ad0193819039` |

```sh
az account set --subscription <id>
```

### Step 3 — Trigger GitHub Actions build

Dispatch the build workflow with the selected project as input:

```sh
gh workflow run build-and-push.yml --ref main --field project=<project>
```

Wait briefly for GitHub to register the new run, then capture its ID:

```sh
sleep 5 && gh run list --workflow=build-and-push.yml --limit=1 --json databaseId --jq '.[0].databaseId'
```

Watch the run until it completes:

```sh
gh run watch <run-id>
```

If the workflow **fails**: print the run URL (`https://github.com/lakhi/health-research-agent-api/actions/runs/<run-id>`) and stop — do not proceed to the container app update.

### Step 4 — Force Container App to pull new image

Project values:

| Project   | Container App     | Resource Group | Image                                              |
|-----------|-------------------|----------------|----------------------------------------------------|
| hex-gig   | hex-gig-agent-api | healthsociety  | `hexgigacr.azurecr.io/hex-gig-agent-api:latest`   |
| vax-study | marhinovirus-api  | vax-study      | `vaxacr.azurecr.io/health-research-api:latest`     |

```sh
az containerapp update \
  --name <app-name> \
  --resource-group <rg> \
  --image <image> \
  --revision-suffix "$(date +%d)-$(date +%b | tr '[:upper:]' '[:lower:]')-$((RANDOM % 10))"
```

The `--revision-suffix` forces a new revision, causing Azure to pull a fresh copy of the `:latest` image from ACR even though the image tag hasn't changed.

### Step 4b — hex-gig only: bump the RSS-refresh job image

The scheduled Container Apps Job `hex-gig-rss-refresh` (daily RSS refresh + metrics purge, 12:00 UTC)
pins a commit-SHA image tag, so it must be bumped alongside every hex-gig deploy or it goes stale:

```sh
SHA=$(gh run view <run-id> --json headSha --jq .headSha)
az containerapp job update \
  --name hex-gig-rss-refresh \
  --resource-group healthsociety \
  --image "hexgigacr.azurecr.io/hex-gig-agent-api:$SHA"
```

Skip this step for vax-study / ssc-psych.

### Step 5 — Verify startup

Tail the container logs and watch for `Application startup complete.`:

```sh
az containerapp logs show -g <rg> -n <app-name> --tail 100 --follow
```

Once confirmed, print a final summary:

```
Project:         <project>
Container App:   <app-name>
Resource Group:  <rg>
Image:           <image>
GH Run:          https://github.com/lakhi/health-research-agent-api/actions/runs/<run-id>
Status:          ✅ Deployment complete
```

## Notes

- **VAX pre-condition:** The GitHub repo must have `VAX_ACR_LOGIN_SERVER`, `VAX_ACR_USERNAME`, and `VAX_ACR_PASSWORD` set as repository secrets before a vax-study build can succeed. If they're missing, the GH Actions run will fail at Step 3 and the skill will exit.
- **Tenant:** Always use `--tenant azure.univie.ac.at` for login — this is the University of Vienna Azure tenant.
- **Image tag stays `:latest`** — the `--revision-suffix` trick (not a tag change) is what triggers the fresh pull.
