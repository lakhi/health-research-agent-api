param containerapps_hex_gig_agent_api_name string = 'hex-gig-agent-api'
param managedEnvironments_hex_gig_apps_env_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/healthsociety/providers/Microsoft.App/managedEnvironments/hex-gig-apps-env'

// ── Secrets (passed at deploy time, never stored in repo) ────────────────────
// Deploy with: az deployment group create ... \
//   --parameters dbPassword='...' ucloudShareToken='...' azureOpenAiApiKey='...' azureEmbedderOpenAiApiKey='...' acrPassword='...'
@secure()
param dbPassword string

@secure()
param ucloudShareToken string

@secure()
param azureOpenAiApiKey string

@secure()
param azureEmbedderOpenAiApiKey string

@secure()
param acrPassword string

resource containerapps_hex_gig_agent_api_name_resource 'Microsoft.App/containerapps@2025-02-02-preview' = {
  name: containerapps_hex_gig_agent_api_name
  location: 'Sweden Central'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Dev'
    'Verantwortliche*r': 'Akshay'
  }
  kind: 'containerapps'
  identity: {
    type: 'None'
  }
  properties: {
    managedEnvironmentId: managedEnvironments_hex_gig_apps_env_externalid
    environmentId: managedEnvironments_hex_gig_apps_env_externalid
    workloadProfileName: 'Consumption'
    configuration: {
      secrets: [
        {
          name: 'db-password'
          value: dbPassword
        }
        {
          name: 'ucloud-share-token'
          value: ucloudShareToken
        }
        {
          name: 'azure-openai-api-key'
          value: azureOpenAiApiKey
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
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        exposedPort: 0
        transport: 'Auto'
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
        allowInsecure: false
        clientCertificateMode: 'Ignore'
        stickySessions: {
          affinity: 'none'
        }
      }
      registries: [
        {
          server: 'hexgigacr.azurecr.io'
          username: 'hexgigacr'
          passwordSecretRef: 'acr-password'
        }
      ]
      identitySettings: []
      maxInactiveRevisions: 100
    }
    template: {
      containers: [
        {
          image: 'hexgigacr.azurecr.io/hex-gig-agent-api:latest'
          imageType: 'ContainerImage'
          name: containerapps_hex_gig_agent_api_name
          env: [
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            // ── Project ──────────────────────────────────────────────────────
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
            // ── Azure OpenAI (LLM) ───────────────────────────────────────────
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: 'https://az-openai-healthsociety.openai.azure.com/openai/deployments/gpt-41-dev-healthsoc/chat/completions?api-version=2025-01-01-preview'
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'
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
            // ── Agno ─────────────────────────────────────────────────────────
            // Telemetry disabled: no per-run metadata events to os-api.agno.com.
            // (OS-launch event is suppressed in api/main.py via AgentOS(telemetry=False).)
            // AGNO_API_KEY intentionally removed — monitoring/telemetry are off, so the
            // key was unused; dropping it removes a US-service credential from the app.
            {
              name: 'AGNO_TELEMETRY'
              value: 'false'
            }
            // ── Budget enforcement ───────────────────────────────────────────
            {
              name: 'DAILY_BUDGET_EUR'
              value: '3.0'
            }
            {
              name: 'MODEL_PRICING_INPUT_EUR'
              value: '1.91'
            }
            {
              name: 'MODEL_PRICING_OUTPUT_EUR'
              value: '7.64'
            }
            // ── u:Cloud (Nextcloud) — research paper source ──────────────────
            // Share token supplied as a deploy-time secret (never hard-coded in the
            // repo, which is browsable by network members). Rotate the token in u:Cloud
            // before deploying — the previously committed value is in git history.
            {
              name: 'UCLOUD_SHARE_TOKEN'
              secretRef: 'ucloud-share-token'
            }
            // ── Knowledge loading ────────────────────────────────────────────
            {
              name: 'LOAD_HEX_GIG_KNOWLEDGE'
              value: 'true'
            }
          ]
          resources: {
            cpu: json('1.25')
            memory: '2.5Gi'
          }
          probes: [
            // Knowledge loading from u:Cloud blocks port 8000 for ~10 min.
            // initialDelaySeconds is capped at 60 by Container Apps.
            // 60s delay + 90 × 10s = 960s (~16 min) total startup tolerance.
            {
              type: 'Startup'
              tcpSocket: {
                port: 8000
              }
              initialDelaySeconds: 60
              periodSeconds: 10
              failureThreshold: 90
              timeoutSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
        cooldownPeriod: 300
        pollingInterval: 30
        rules: [
          {
            name: 'http-scaler'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
      volumes: []
    }
  }
}
