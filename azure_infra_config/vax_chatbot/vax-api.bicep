param containerapps_vax_api_name string = 'marhinovirus-api'
param managedEnvironments_vax_env_externalid string = '/subscriptions/44365843-c70c-4844-a430-ad0193819039/resourceGroups/vax-study/providers/Microsoft.App/managedEnvironments/vax-env'

@secure()
param dbPassword string

@secure()
param agnoApiKey string

@secure()
param azureOpenAiApiKey string

@secure()
param azureEmbedderOpenAiApiKey string

@secure()
param acrPassword string

resource containerapps_vax_api_resource 'Microsoft.App/containerapps@2025-02-02-preview' = {
  name: containerapps_vax_api_name
  location: 'Sweden Central'
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
    managedEnvironmentId: managedEnvironments_vax_env_externalid
    environmentId: managedEnvironments_vax_env_externalid
    workloadProfileName: 'Consumption'
    configuration: {
      secrets: [
        {
          name: 'db-password'
          value: dbPassword
        }
        {
          name: 'agno-api-key'
          value: agnoApiKey
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
          server: 'vaxacr.azurecr.io'
          username: 'vaxacr'
          passwordSecretRef: 'acr-password'
        }
      ]
      identitySettings: []
      maxInactiveRevisions: 100
    }
    template: {
      containers: [
        {
          image: 'vaxacr.azurecr.io/health-research-api:latest'
          imageType: 'ContainerImage'
          name: containerapps_vax_api_name
          env: [
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
            {
              name: 'PROJECT_NAME'
              value: 'vax-study'
            }
            {
              name: 'DB_HOST'
              value: 'vax-db.postgres.database.azure.com'
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
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: 'https://az-openai-vax-models.openai.azure.com/openai/deployments/gpt-4.1-vax-study/chat/completions?api-version=2025-01-01-preview'
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_ENDPOINT'
              value: 'https://az-openai-vax-models.openai.azure.com/'
            }
            {
              name: 'AZURE_EMBEDDER_DEPLOYMENT'
              value: 'embedding-3-large-vax-study'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_VERSION'
              value: '2024-02-01'
            }
            {
              name: 'AZURE_EMBEDDER_OPENAI_API_KEY'
              secretRef: 'azure-embedder-openai-api-key'
            }
            {
              name: 'AGNO_API_KEY'
              secretRef: 'agno-api-key'
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

output fqdn string = containerapps_vax_api_resource.properties.configuration.ingress.fqdn
