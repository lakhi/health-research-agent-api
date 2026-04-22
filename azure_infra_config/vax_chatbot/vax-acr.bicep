param registries_vax_acr_name string = 'vaxacr'

resource registries_vax_acr_name_resource 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registries_vax_acr_name
  location: 'swedencentral'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Test'
    'Verantwortliche*r': 'Akshay'
  }
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
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
    }
    encryption: {
      status: 'disabled'
    }
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
  }
}

output loginServer string = registries_vax_acr_name_resource.properties.loginServer
