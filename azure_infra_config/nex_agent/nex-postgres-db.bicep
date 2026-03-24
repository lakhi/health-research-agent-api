param flexibleServers_nex_postgres_db_name string = 'nex-postgres-db'

resource flexibleServers_nex_postgres_db_name_resource 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: flexibleServers_nex_postgres_db_name
  location: 'Sweden Central'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Dev'
    'Verantwortliche*r': 'Akshay'
  }
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: 'postgres'
    administratorLoginPassword: 'REPLACE_WITH_SECURE_PASSWORD'
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

resource flexibleServers_nex_postgres_db_firewall_akshay 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: flexibleServers_nex_postgres_db_name_resource
  name: 'akshays_macbookpro'
  properties: {
    startIpAddress: '77.80.3.180'
    endIpAddress: '77.80.3.180'
  }
}

resource flexibleServers_nex_postgres_db_firewall_azure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: flexibleServers_nex_postgres_db_name_resource
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource flexibleServers_nex_postgres_db_config 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: flexibleServers_nex_postgres_db_name_resource
  name: 'azure.extensions'
  properties: {
    value: 'vector'
    source: 'user-override'
  }
}
