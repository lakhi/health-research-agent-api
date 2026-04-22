param flexibleServers_vax_postgres_db_name string = 'vax-db'

@secure()
param administratorLoginPassword string

resource flexibleServers_vax_postgres_db_resource 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: flexibleServers_vax_postgres_db_name
  location: 'Sweden Central'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Test'
    'Verantwortliche*r': 'Akshay'
  }
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: 'postgres'
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    maintenanceWindow: {
      customWindow: 'Disabled'
      dayOfWeek: 0
      startHour: 0
      startMinute: 0
    }
    version: '16'
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
  }
}

resource flexibleServers_vax_postgres_firewall_azure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: flexibleServers_vax_postgres_db_resource
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource flexibleServers_vax_postgres_config_extensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: flexibleServers_vax_postgres_db_resource
  name: 'azure.extensions'
  properties: {
    value: 'vector'
    source: 'user-override'
  }
}

output fqdn string = flexibleServers_vax_postgres_db_resource.properties.fullyQualifiedDomainName
