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

To deploy to Azure:

1. Linux Upgrade
```sh
./scripts/generate_requirements.sh linux-upgrade
```
2. Enable the `build-and-push.yml` workflow action for automatic Azure deployment
3. Commit and deploy (will trigger Github Actions)
