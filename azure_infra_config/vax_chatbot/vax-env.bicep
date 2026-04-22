param logAnalytics_vax_logs_name string = 'vax-logs'
param managedEnvironments_vax_env_name string = 'vax-env'

resource logAnalytics_vax_logs_resource 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalytics_vax_logs_name
  location: 'swedencentral'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Test'
    'Verantwortliche*r': 'Akshay'
  }
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource managedEnvironments_vax_env_resource 'Microsoft.App/managedEnvironments@2025-02-02-preview' = {
  name: managedEnvironments_vax_env_name
  location: 'swedencentral'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Test'
    'Verantwortliche*r': 'Akshay'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics_vax_logs_resource.properties.customerId
        sharedKey: logAnalytics_vax_logs_resource.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    zoneRedundant: false
  }
}

output environmentId string = managedEnvironments_vax_env_resource.id
output environmentPrincipalId string = managedEnvironments_vax_env_resource.identity.principalId
output defaultDomain string = managedEnvironments_vax_env_resource.properties.defaultDomain
