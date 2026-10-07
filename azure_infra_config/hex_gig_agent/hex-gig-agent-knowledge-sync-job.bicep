// The single writer of the HeX knowledge tables (#42): mirrors u:Cloud papers, the members CSV
// and the news feed into the knowledge base, builds the vector index, and purges old usage metrics.
// The API never loads knowledge.
param jobs_hex_gig_knowledge_sync_name string = 'hex-gig-knowledge-sync'
param managedEnvironments_hex_gig_apps_env_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/healthsociety/providers/Microsoft.App/managedEnvironments/hex-gig-apps-env'

// ── Secrets (passed at deploy time, never stored in repo) ────────────────────
// Deploy with: az deployment group create ... \
//   --parameters dbPassword='...' azureEmbedderOpenAiApiKey='...' ucloudShareToken='...' acrPassword='...'
@secure()
param dbPassword string

@secure()
param azureEmbedderOpenAiApiKey string

@secure()
param ucloudShareToken string

@secure()
param acrPassword string

// ── Schedule ────────────────────────────────────────────────────────────────
// Cron expressions in Container Apps Jobs are interpreted in UTC (no timeZone field).
// 12:00 UTC = 13:00 Europe/Vienna in winter (CET) / 14:00 in summer (CEST), the time the job has run
// at since June 2026. A run where nothing changed takes about a minute and writes nothing; start it
// on demand after a u:Cloud intake: az containerapp job start -n hex-gig-knowledge-sync -g healthsociety
param cronExpression string = '0 12 * * *'

resource jobs_hex_gig_knowledge_sync_resource 'Microsoft.App/jobs@2025-02-02-preview' = {
  name: jobs_hex_gig_knowledge_sync_name
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
      // A from-scratch load (empty tables) embeds every paper and takes hours, not minutes. A
      // retry is safe: the sync resumes where it stopped, because unfinished documents are re-done.
      replicaTimeout: 14400
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
          name: 'ucloud-share-token'
          value: ucloudShareToken
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
          name: jobs_hex_gig_knowledge_sync_name
          // As a module so the repository root (/app) is on sys.path.
          command: [
            'python'
            '-m'
            'scripts.sync_hex_gig_knowledge'
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
              value: 'https://az-openai-healthsociety.openai.azure.com/openai/deployments/embedding-large-dev-healthsoc/embeddings?api-version=2023-05-15'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_VERSION'
              value: '2023-05-15'
            }
            {
              name: 'AZURE_EMBEDDER_DEPLOYMENT'
              value: 'embedding-large-dev-healthsoc'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_KEY'
              secretRef: 'azure-embedder-openai-api-key'
            }
            // ── u:Cloud (Nextcloud) — research paper source ──────────────────
            {
              name: 'UCLOUD_SHARE_TOKEN'
              secretRef: 'ucloud-share-token'
            }
            // ── Agno ─────────────────────────────────────────────────────────
            {
              name: 'AGNO_TELEMETRY'
              value: 'false'
            }
            // ── Metrics retention ────────────────────────────────────────────
            // This daily job also purges agent_usage_metrics rows older than N days
            // (anonymous, content-free) to bound retention. See scripts/sync_hex_gig_knowledge.py.
            {
              name: 'METRICS_RETENTION_DAYS'
              value: '180'
            }
          ]
          // PDF chunking loads a local sentence-embedding model; 2 GiB leaves room for it and
          // for parsing large PDFs. Billed only while a run is active.
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
        }
      ]
    }
  }
}
