param containerapps_nex_agent_api_name string = 'nex-agent-api'
param managedEnvironments_nex_apps_env_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/healthsociety/providers/Microsoft.App/managedEnvironments/nex-apps-env'

resource containerapps_nex_agent_api_name_resource 'Microsoft.App/containerapps@2025-02-02-preview' = {
  name: containerapps_nex_agent_api_name
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
    managedEnvironmentId: managedEnvironments_nex_apps_env_externalid
    environmentId: managedEnvironments_nex_apps_env_externalid
    workloadProfileName: 'Consumption'
    configuration: {
      secrets: [
        {
          name: 'agno-api-key'
        }
        {
          name: 'azure-openai-api-key'
        }
        {
          name: 'azure-embedder-openai-api-key'
        }
        {
          name: 'db-password'
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
          server: 'nex-acr.azurecr.io'
          identity: 'system-environment'
        }
      ]
      identitySettings: []
      maxInactiveRevisions: 100
    }
    template: {
      containers: [
        {
          image: 'nex-acr.azurecr.io/nex-agent-api:latest'
          imageType: 'ContainerImage'
          name: containerapps_nex_agent_api_name
          env: [
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            {
              name: 'DB_HOST'
              value: 'nex-postgres-db.postgres.database.azure.com'
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
              name: 'AZURE_OPENAI_ENDPOINT'
              value: 'https://az-openai-nex.openai.azure.com/openai/deployments/gpt-41-nex/chat/completions?api-version=2025-01-01-preview'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_ENDPOINT'
              value: 'https://az-openai-nex.openai.azure.com/openai/deployments/embedding-large-nex/embeddings?api-version=2023-05-15'
            }
            {
              name: 'DB_PASS'
              secretRef: 'db-password'
            }
            {
              name: 'AGNO_API_KEY'
              secretRef: 'agno-api-key'
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_KEY'
              secretRef: 'azure-embedder-openai-api-key'
            }
          ]
          resources: {
            cpu: json('1.25')
            memory: '2.5Gi'
          }
          probes: []
        }
      ]
      scale: {
        minReplicas: 0
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
