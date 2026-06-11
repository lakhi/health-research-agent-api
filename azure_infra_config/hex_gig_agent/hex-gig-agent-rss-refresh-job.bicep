param jobs_hex_gig_rss_refresh_name string = 'hex-gig-rss-refresh'
param managedEnvironments_hex_gig_apps_env_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/healthsociety/providers/Microsoft.App/managedEnvironments/hex-gig-apps-env'

// ── Secrets (passed at deploy time, never stored in repo) ────────────────────
// Deploy with: az deployment group create ... \
//   --parameters dbPassword='...' azureEmbedderOpenAiApiKey='...' acrPassword='...'
@secure()
param dbPassword string

@secure()
param azureEmbedderOpenAiApiKey string

@secure()
param acrPassword string

// ── Schedule ────────────────────────────────────────────────────────────────
// Cron expressions in Container Apps Jobs are interpreted in UTC (no timeZone field).
// 05:00 UTC = 06:00 Europe/Vienna in winter (CET) / 07:00 in summer (CEST).
// We accept the ±1 h DST drift for a daily news refresh.
param cronExpression string = '0 5 * * *'

resource jobs_hex_gig_rss_refresh_resource 'Microsoft.App/jobs@2025-02-02-preview' = {
  name: jobs_hex_gig_rss_refresh_name
  location: 'Sweden Central'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Dev'
    'Verantwortliche*r': 'Akshay'
  }
  properties: {
    environmentId: managedEnvironments_hex_gig_apps_env_externalid
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 600
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: cronExpression
        parallelism: 1
        replicaCompletionCount: 1
      }
      secrets: [
        {
          name: 'db-password'
          value: dbPassword
        }
        {
          name: 'azure-embedder-openai-api-key'
          value: azureEmbedderOpenAiApiKey
        }
        {
          name: 'acr-password'
          value: acrPassword
        }
      ]
      registries: [
        {
          server: 'hexgigacr.azurecr.io'
          username: 'hexgigacr'
          passwordSecretRef: 'acr-password'
        }
      ]
    }
    template: {
      containers: [
        {
          image: 'hexgigacr.azurecr.io/hex-gig-agent-api:latest'
          imageType: 'ContainerImage'
          name: jobs_hex_gig_rss_refresh_name
          command: [
            'python'
            'scripts/refresh_hex_gig_rss.py'
          ]
          env: [
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            {
              name: 'PROJECT_NAME'
              value: 'hex_gig'
            }
            // ── Database ─────────────────────────────────────────────────────
            {
              name: 'DB_HOST'
              value: 'hex-gig-postgres-db.postgres.database.azure.com'
            }
            {
              name: 'DB_PORT'
              value: '5432'
            }
            {
              name: 'DB_USER'
              value: 'postgres'
            }
            {
              name: 'DB_DATABASE'
              value: 'postgres'
            }
            {
              name: 'DB_PASS'
              secretRef: 'db-password'
            }
            // ── Azure OpenAI (Embedder) ──────────────────────────────────────
            {
              name: 'AZURE_EMBEDDER_OPENAI_ENDPOINT'
              value: 'https://az-openai-nex.openai.azure.com/openai/deployments/embedding-large-nex/embeddings?api-version=2023-05-15'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_VERSION'
              value: '2023-05-15'
            }
            {
              name: 'AZURE_EMBEDDER_DEPLOYMENT'
              value: 'embedding-large-nex'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_KEY'
              secretRef: 'azure-embedder-openai-api-key'
            }
            // ── Agno ─────────────────────────────────────────────────────────
            {
              name: 'AGNO_TELEMETRY'
              value: 'false'
            }
            // ── Metrics retention ────────────────────────────────────────────
            // This daily job also purges agent_usage_metrics rows older than N days
            // (anonymous, content-free) to bound retention. See scripts/refresh_hex_gig_rss.py.
            {
              name: 'METRICS_RETENTION_DAYS'
              value: '180'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}
