# Azure Deployment Guide

This guide covers deploying the Health Research Agent API to Azure using Docker containers.

## Prerequisites

- Azure CLI installed and logged in
- Docker installed
- Azure Container Registry (ACR) or Docker Hub account
- Azure PostgreSQL Flexible Server configured

## Setup Environment Files

1. **Create environment files from templates:**
   ```bash
   ./switch_env.sh setup
   ```

2. **Configure local environment (.env.local):**
   - Edit `.env.local` with your local development values
   - Use `localhost` for DB_HOST when using Docker Compose

3. **Configure Azure environment (.env.azure):**
   - Edit `.env.azure` with your Azure production values
   - Use your Azure PostgreSQL server hostname
   - URL-encode special characters in passwords

## Local Development

1. **Switch to local environment:**
   ```bash
   ./switch_env.sh local
   ```

2. **Start local development environment:**
   ```bash
   docker compose up
   ```

## Azure Deployment

### Option 1: Azure Container Instances

1. **Build Azure Docker image:**
   ```bash
   ./switch_env.sh build
   ```

2. **Push to container registry:**
   ```bash
   # Tag for your registry
   docker tag health-research-agent-api:latest <your-registry>.azurecr.io/health-research-agent-api:latest
   
   # Push to registry
   docker push <your-registry>.azurecr.io/health-research-agent-api:latest
   ```

3. **Deploy to Azure Container Instances:**
   ```bash
   # Edit azure-container-instance.template.yaml with your values
   cp azure-container-instance.template.yaml azure-container-instance.yaml
   # Fill in placeholders: <your-registry>, <your-db-server>, etc.
   
   # Deploy
   az container create --resource-group <your-rg> --file azure-container-instance.yaml
   ```

### Option 2: Azure App Service

1. **Build and push Docker image** (same as above)

2. **Deploy to App Service:**
   ```bash
   # Edit azure-app-service.template.json with your values
   cp azure-app-service.template.json azure-app-service.json
   # Fill in placeholders and configure KeyVault references
   
   # Create App Service
   az webapp create --resource-group <your-rg> --plan <your-plan> --name <your-app> --deployment-container-image-name <your-registry>.azurecr.io/health-research-agent-api:latest
   ```

## Environment Switching Commands

| Command | Description |
|---------|-------------|
| `./switch_env.sh setup` | Create environment files from templates |
| `./switch_env.sh local` | Switch to local development environment |
| `./switch_env.sh azure` | Switch to Azure production environment |
| `./switch_env.sh build` | Build Docker image for Azure deployment |
| `./switch_env.sh deploy` | Test Azure configuration locally |

## Security Best Practices

1. **Never commit actual .env files** - Only templates are tracked in git
2. **Use Azure Key Vault** for production secrets (see azure-app-service.template.json)
3. **Enable Azure PostgreSQL SSL** in production
4. **Use managed identities** when possible instead of connection strings

## Database Configuration

- **Local**: Uses Docker PostgreSQL container with pgvector
- **Azure**: Uses Azure Database for PostgreSQL Flexible Server
- **SSL**: Automatically enabled for Azure, disabled for local development

## Testing Azure Configuration Locally

To test your Azure environment configuration without deploying:

```bash
./switch_env.sh deploy
```

This will:
- Build the Azure Docker image
- Run it locally on port 8001
- Connect to your actual Azure PostgreSQL database
- Show logs for debugging

Access the test deployment at: http://localhost:8001

## Troubleshooting

### Database Connection Issues
- Verify Azure PostgreSQL allows connections from your IP
- Check if pgvector extension is enabled in Azure
- Ensure password is URL-encoded in .env.azure

### Docker Build Issues
- Make sure all dependencies are in requirements.txt
- Check Docker daemon is running
- Verify base image availability

### Environment File Issues
- Run `./switch_env.sh setup` to recreate templates
- Check file permissions: `chmod +x switch_env.sh`
- Verify no trailing spaces in environment variables
