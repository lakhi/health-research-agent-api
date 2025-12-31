param containerapps_chatbot_api_healthsoc_name string = 'healthsoc-chatbot-api'
param managedEnvironments_healthsoc_apps_env_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/healthsociety/providers/Microsoft.App/managedEnvironments/healthsoc-apps-env'

resource containerapps_chatbot_api_healthsoc_name_resource 'Microsoft.App/containerapps@2025-02-02-preview' = {
  name: containerapps_chatbot_api_healthsoc_name
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
    managedEnvironmentId: managedEnvironments_healthsoc_apps_env_externalid
    environmentId: managedEnvironments_healthsoc_apps_env_externalid
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
          server: 'healthsocietydev.azurecr.io'
          identity: 'system-environment'
        }
      ]
      identitySettings: []
      maxInactiveRevisions: 100
    }
    template: {
      containers: [
        {
          image: 'healthsocietydev.azurecr.io/health-research-api:latest'
          imageType: 'ContainerImage'
          name: containerapps_chatbot_api_healthsoc_name
          env: [
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            {
              name: 'DB_HOST'
              value: 'postgres-db-healthsoc.postgres.database.azure.com'
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
              value: 'https://az-openai-healthsociety.openai.azure.com/openai/deployments/gpt-41-dev-healthsoc/chat/completions?api-version=2025-01-01-preview'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_ENDPOINT'
              value: 'https://az-openai-healthsociety.openai.azure.com/openai/deployments/embedding-large-dev-healthsoc/embeddings?api-version=2023-05-15'
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
