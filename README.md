# Health Research Agent API

A FastAPI-based application for the **Health Research Network's Chatbot project** and the **Social Econ Psych research group studies** at Uni Wien.

## Setup

### 1. Generate Requirements

Generate `requirements.txt` from `pyproject.toml`:

```sh
./scripts/generate_requirements.sh
```

To upgrade all dependencies to their latest compatible versions:
```sh
./scripts/generate_requirements.sh upgrade
```

```sh
./scripts/generate_requirements.sh linux-upgrade
```

For Linux deployment:
```sh
./scripts/generate_requirements.sh linux
```

### 2. Switch Environment

Switch between local and Azure environments:

```sh
./scripts/switch_env.sh local   # For local development
./scripts/switch_env.sh azure   # For Azure deployment
```

### 3. Development Setup

Create virtual environment and install dependencies (run after generating requirements):

```sh
./scripts/dev_setup.sh
```

Then activate the virtual environment:

```sh
source .venv/bin/activate
```

## Running the Application

### Local Development

Start the application with Docker:

```sh
docker compose up -d
```

In case of any requirements or Dockerfile changes:

```sh
docker compose up -d --build
```

View logs:

```sh
docker logs -f health-research-agent-api-api-1
```

### Azure Deployment

View Azure Container App logs:

```sh
az containerapp logs show --name health-research-api --resource-group health_research_network --type console --follow
```

## Deployment to Azure

To deploy to ACR:

1. Linux Upgrade
```sh
./scripts/generate_requirements.sh linux-upgrade
```
2. Enable the `build-and-push.yml` workflow action for automatic Azure deployment
3. Commit and deploy (will trigger Github Actions)

To deploy to Azure Container Apps (Vax study daily deployments):

1. deploy with env variable
az containerapp update \
  --name marhinovirus-study-api \
  --resource-group socialeconpsyresearch \
  --image socialeconpsy-drdfgfb2g7aadtgk.azurecr.io/health-research-api:latest \
  --revision-suffix v1-a1 \
  --set-env-vars PROJECT_NAME=vax-study

2. verify the revisions are healthy
az containerapp revision list \
  --name marhinovirus-study-api \
  --resource-group socialeconpsyresearch \
  --output table

3. remove the label on the older versions
az containerapp revision label remove \
  --name marhinovirus-study-api \
  --resource-group socialeconpsyresearch \
  --label v1-1

4. add it to the new version
az containerapp revision label add \
  --name marhinovirus-study-api \
  --resource-group socialeconpsyresearch \
  --revision marhinovirus-study-api--v1-a1 \
  --label v1-1

5. verify new labels
az containerapp ingress traffic show \
  --name marhinovirus-study-api \
  --resource-group socialeconpsyresearch

6. deactivate older revisions
az containerapp revision deactivate --name marhinovirus-study-api --resource-group socialeconpsyresearch --revision marhinovirus-study-api--v1-a
