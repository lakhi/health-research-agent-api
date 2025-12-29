param flexibleServers_azure_db_hrn_name string = 'azure-db-hrn'

@secure()
@description('Administrator login password')
param administratorLoginPassword string

resource flexibleServers_azure_db_hrn_name_resource 'Microsoft.DBforPostgreSQL/flexibleServers@2025-01-01-preview' = {
  name: flexibleServers_azure_db_hrn_name
  location: 'West Europe'
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
    replica: {
      role: 'Primary'
    }
    storage: {
      iops: 120
      tier: 'P4'
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    dataEncryption: {
      type: 'SystemManaged'
    }
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
    version: '16'
    administratorLogin: 'postgres'
    administratorLoginPassword: administratorLoginPassword
    availabilityZone: '3'
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
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
    replicationRole: 'Primary'
  }
}

resource flexibleServers_azure_db_hrn_name_Default 'Microsoft.DBforPostgreSQL/flexibleServers/advancedThreatProtectionSettings@2025-01-01-preview' = {
  parent: flexibleServers_azure_db_hrn_name_resource
  name: 'Default'
  properties: {
    state: 'Disabled'
  }
}

resource flexibleServers_azure_db_hrn_name_akshays_macbookpro 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-01-01-preview' = {
  parent: flexibleServers_azure_db_hrn_name_resource
  name: 'akshays_macbookpro'
  properties: {
    startIpAddress: '77.80.3.180'
    endIpAddress: '77.80.3.180'
  }
}

resource flexibleServers_azure_db_hrn_name_AllowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-01-01-preview' = {
  parent: flexibleServers_azure_db_hrn_name_resource
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}
