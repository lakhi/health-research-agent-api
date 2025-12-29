param containerapps_health_research_api_name string = 'health-research-api'
param managedEnvironments_hrn_env_dev_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/health_research_network/providers/Microsoft.App/managedEnvironments/hrn-env-dev'

resource containerapps_health_research_api_name_resource 'Microsoft.App/containerapps@2025-02-02-preview' = {
  name: containerapps_health_research_api_name
  location: 'West Europe'
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
    managedEnvironmentId: managedEnvironments_hrn_env_dev_externalid
    environmentId: managedEnvironments_hrn_env_dev_externalid
    workloadProfileName: 'Consumption'
    configuration: {
      secrets: [
        {
          name: 'google-api-key'
        }
        {
          name: 'agno-api-key'
        }
        {
          name: 'azure-openai-api-key'
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
        stickySessions: {
          affinity: 'none'
        }
      }
      registries: [
        {
          server: 'hrndev.azurecr.io'
          identity: 'system-environment'
        }
      ]
      identitySettings: []
      maxInactiveRevisions: 100
    }
    template: {
      containers: [
        {
          image: 'hrndev.azurecr.io/${containerapps_health_research_api_name}:latest'
          imageType: 'ContainerImage'
          name: containerapps_health_research_api_name
          env: [
            {
              name: 'ENVIRONMENT'
              value: 'development'
            }
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            {
              name: 'DB_HOST'
              value: 'azure-db-hrn.postgres.database.azure.com'
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
              value: 'https://azure-openai-hrn.openai.azure.com/openai/deployments/gpt-4o_hrn-agent/chat/completions?api-version=2025-01-01-preview'
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
              name: 'GOOGLE_API_KEY'
              secretRef: 'google-api-key'
            }
          ]
          resources: {
            cpu: json('1.25')
            memory: '2.5Gi'
          }
          probes: [
            {
              type: 'Startup'
              failureThreshold: 10
              httpGet: {
                path: 'v1/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 60
              periodSeconds: 10
              successThreshold: 1
              timeoutSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
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
