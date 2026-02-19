param containerapps_marhinovirus_study_api_name string = 'marhinovirus-study-api'
param managedEnvironments_socialeconpsy_env_externalid string = '/subscriptions/444c1e5c-ac0d-4420-94ea-d4a5414d20e1/resourceGroups/socialeconpsyresearch/providers/Microsoft.App/managedEnvironments/socialeconpsy-env'

resource containerapps_marhinovirus_study_api_name_resource 'Microsoft.App/containerapps@2025-02-02-preview' = {
  name: containerapps_marhinovirus_study_api_name
  location: 'West Europe'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Test'
    'Verantwortliche*r': 'Akshay'
  }
  kind: 'containerapps'
  identity: {
    type: 'None'
  }
  properties: {
    managedEnvironmentId: managedEnvironments_socialeconpsy_env_externalid
    environmentId: managedEnvironments_socialeconpsy_env_externalid
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
          name: 'db-password'
        }
        {
          name: 'azure-embedder-openai-api-key'
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
          server: 'socialeconpsy-drdfgfb2g7aadtgk.azurecr.io'
          identity: 'system-environment'
        }
      ]
      identitySettings: []
      maxInactiveRevisions: 100
    }
    template: {
      containers: [
        {
          image: 'socialeconpsy-drdfgfb2g7aadtgk.azurecr.io/health-research-api:latest'
          imageType: 'ContainerImage'
          name: containerapps_marhinovirus_study_api_name
          env: [
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            {
              name: 'DB_HOST'
              value: 'socialeconpsy-postgres-db.postgres.database.azure.com'
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
              value: 'https://az-openai-socialeconpsy.openai.azure.com/openai/deployments/gpt-4o-marhinovirus/chat/completions?api-version=2025-01-01-preview'
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
              name: 'PROJECT_NAME'
              value: 'vax-study'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_ENDPOINT'
              value: 'https://az-openai-healthsociety.openai.azure.com'
            }
            {
              name: 'AZURE_EMBEDDER_DEPLOYMENT'
              value: 'embedding-large-dev-healthsoc'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_VERSION'
              value: '2024-02-01'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_KEY'
              secretRef: 'azure-embedder-openai-api-key'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: []
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
