param registries_nex_acr_name string = 'nex-acr'

resource registries_nex_acr_name_resource 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registries_nex_acr_name
  location: 'swedencentral'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Dev'
    'Verantwortliche*r': 'Akshay'
  }
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      trustPolicy: {
        type: 'Notary'
        status: 'disabled'
      }
      retentionPolicy: {
        days: 7
        status: 'disabled'
      }
      exportPolicy: {
        status: 'enabled'
      }
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
      softDeletePolicy: {
        retentionDays: 7
        status: 'disabled'
      }
    }
    encryption: {
      status: 'disabled'
    }
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
    anonymousPullEnabled: false
    metadataSearch: 'Disabled'
  }
}

resource registries_nex_acr_admin_scopemap 'Microsoft.ContainerRegistry/registries/scopeMaps@2023-07-01' = {
  parent: registries_nex_acr_name_resource
  name: '_repositories_admin'
  properties: {
    description: 'Can perform all read, write and delete operations on the registry'
    actions: [
      'repositories/*/content/delete'
      'repositories/*/content/read'
      'repositories/*/content/write'
      'repositories/*/metadata/read'
      'repositories/*/metadata/write'
    ]
  }
}

resource registries_nex_acr_pull_scopemap 'Microsoft.ContainerRegistry/registries/scopeMaps@2023-07-01' = {
  parent: registries_nex_acr_name_resource
  name: '_repositories_pull'
  properties: {
    description: 'Can pull any repository of the registry'
    actions: [
      'repositories/*/content/read'
    ]
  }
}

resource registries_nex_acr_push_scopemap 'Microsoft.ContainerRegistry/registries/scopeMaps@2023-07-01' = {
  parent: registries_nex_acr_name_resource
  name: '_repositories_push'
  properties: {
    description: 'Can push to any repository of the registry'
    actions: [
      'repositories/*/content/read'
      'repositories/*/content/write'
    ]
  }
}

resource registries_nex_acr_metadata_scopemap 'Microsoft.ContainerRegistry/registries/scopeMaps@2023-07-01' = {
  parent: registries_nex_acr_name_resource
  name: '_repositories_pull_metadata_read'
  properties: {
    description: 'Can perform all read operations on the registry'
    actions: [
      'repositories/*/content/read'
      'repositories/*/metadata/read'
    ]
  }
}
