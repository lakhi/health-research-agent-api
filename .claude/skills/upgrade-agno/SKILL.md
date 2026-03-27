---
name: upgrade-agno
description: "Check the latest agno release on GitHub and, if newer than the pinned version, upgrade requirements.txt and requirements-linux.txt, rebuild the dev venv and Docker image, verify the app starts cleanly, then commit and push."
argument-hint: ""
user-invocable: true
---

# Upgrade Agno

Upgrade the pinned agno version across both requirements files, verify the Docker build starts cleanly, and commit the result.

## Inputs

No arguments required.

## Files Updated

- `requirements.txt`
- `requirements-linux.txt`

## Procedure

### Step 0 — Version check

1. Fetch https://github.com/agno-agi/agno/releases and extract the latest release version (e.g. `v2.5.12` → `2.5.12`).
2. Run `grep "^agno==" requirements.txt` to extract the currently pinned version.
3. Compare the two versions using standard semantic versioning order.
   - If pinned version is already equal to or ahead of the latest release: report "agno is already up to date (agno==X.Y.Z)" and **stop** — do not run any scripts.
   - If the latest release is newer: report both versions (current and latest) and proceed.

### Step 1 — Upgrade requirements (macOS / local)

```bash
./scripts/generate_requirements.sh upgrade
```

After the script completes, run `grep "^agno==" requirements.txt` and report the new pinned version to confirm the upgrade landed.

### Step 2 — Rebuild dev venv

```bash
./scripts/dev_setup.sh
```

### Step 3 — Rebuild Docker image and verify startup

```bash
docker compose up -d --build
```

Wait 5 seconds, then fetch logs:

```bash
sleep 5 && docker compose logs --tail=80
```

Automatically inspect the log output:

- **Success**: "Application started successfully" (or equivalent startup confirmation line) is present and no `ERROR`-level lines appear → proceed to Step 4.
- **Failure**: Error lines are present or the startup confirmation is absent → **stop**, report the relevant log lines, and propose a concrete fix plan. Do not proceed to Step 4 until the issue is resolved.

### Step 4 — Upgrade requirements (Linux / Azure)

```bash
./scripts/generate_requirements.sh linux-upgrade
```

### Step 5 — Commit and push

Stage both requirements files:

```bash
git add requirements.txt requirements-linux.txt
```

Use the `commit-commands:commit` skill with commit message:

```
chore(deps): upgrade agno to vX.Y.Z
```

Replace `X.Y.Z` with the actual new version. Then push:

```bash
git push
```

## Decision Rules

- Never run the upgrade scripts if agno is already at the latest version.
- Never proceed past Step 3 if Docker logs show errors or the app did not reach its started state.
- Stage only `requirements.txt` and `requirements-linux.txt` — do not stage unrelated changes.
- Do not open a pull request; push directly to the current branch.

## References

- Agno releases: https://github.com/agno-agi/agno/releases
