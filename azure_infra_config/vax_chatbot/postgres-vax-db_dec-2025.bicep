param flexibleServers_socialeconpsy_postgres_db_name string = 'socialeconpsy-postgres-db'

resource flexibleServers_socialeconpsy_postgres_db_name_resource 'Microsoft.DBforPostgreSQL/flexibleServers@2025-01-01-preview' = {
  name: flexibleServers_socialeconpsy_postgres_db_name
  location: 'West Europe'
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

resource flexibleServers_socialeconpsy_postgres_db_name_Default 'Microsoft.DBforPostgreSQL/flexibleServers/advancedThreatProtectionSettings@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'Default'
  properties: {
    state: 'Disabled'
  }
}

// Custom PostgreSQL Configurations (user-override only)
resource flexibleServers_socialeconpsy_postgres_db_name_archive_command 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'archive_command'
  properties: {
    value: 'BlobLogUpload.sh %f %p'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_archive_mode 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'archive_mode'
  properties: {
    value: 'always'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_authentication_timeout 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'authentication_timeout'
  properties: {
    value: '30'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_azure_extensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'azure.extensions'
  properties: {
    value: 'vector'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_config_file 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'config_file'
  properties: {
    value: '/datadrive/pg/data/postgresql.conf'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_cron_host 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'cron.host'
  properties: {
    value: '/tmp'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_cron_log_min_messages 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'cron.log_min_messages'
  properties: {
    value: 'warning'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_cron_log_run 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'cron.log_run'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_data_checksums 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'data_checksums'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_data_directory 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'data_directory'
  properties: {
    value: '/datadrive/pg/data'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_data_directory_mode 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'data_directory_mode'
  properties: {
    value: '0700'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_default_toast_compression 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'default_toast_compression'
  properties: {
    value: 'lz4'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_dynamic_library_path 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'dynamic_library_path'
  properties: {
    value: '$libdir'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_escape_string_warning 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'escape_string_warning'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_event_triggers 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'event_triggers'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_external_pid_file 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'external_pid_file'
  properties: {
    value: '/var/run/postgresql/postgresql.pid'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_fsync 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'fsync'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_full_page_writes 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'full_page_writes'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_gin_fuzzy_search_limit 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'gin_fuzzy_search_limit'
  properties: {
    value: '0'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_gin_pending_list_limit 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'gin_pending_list_limit'
  properties: {
    value: '4MB'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_hash_mem_multiplier 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'hash_mem_multiplier'
  properties: {
    value: '1'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_hstore_enabled 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'hstore.enabled'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_ignore_system_indexes 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'ignore_system_indexes'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_jit 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'jit'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_lo_compat_privileges 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'lo_compat_privileges'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_connections 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_connections'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_disconnections 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_disconnections'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_duration 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_duration'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_lock_waits 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_lock_waits'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_min_duration_statement 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_min_duration_statement'
  properties: {
    value: '-1'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_min_error_statement 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_min_error_statement'
  properties: {
    value: 'ERROR'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_min_messages 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_min_messages'
  properties: {
    value: 'WARNING'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_statement 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_statement'
  properties: {
    value: 'none'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_log_statement_sample_rate 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'log_statement_sample_rate'
  properties: {
    value: '1'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pg_hint_plan_debug_print 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pg_hint_plan.debug_print'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pg_hint_plan_enable_hint 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pg_hint_plan.enable_hint'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pg_hint_plan_message_level 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pg_hint_plan.message_level'
  properties: {
    value: 'warning'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pg_stat_statements_max 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pg_stat_statements.max'
  properties: {
    value: '10000'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pg_stat_statements_track 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pg_stat_statements.track'
  properties: {
    value: 'top'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pglogical_synchronize_log_slot 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pglogical.synchronize_log_slot'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_pglogical_use_spi 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'pglogical.use_spi'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_quote_all_identifiers 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'quote_all_identifiers'
  properties: {
    value: 'off'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_wal_buffers 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'wal_buffers'
  properties: {
    value: '2048kB'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_wal_compression 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'wal_compression'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_wal_init_zero 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'wal_init_zero'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_wal_recycle 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'wal_recycle'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

// Database Definition
resource flexibleServers_socialeconpsy_postgres_db_name_postgres 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'postgres'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Firewall Rules
resource flexibleServers_socialeconpsy_postgres_db_name_akshay_mac_IPAddress_2025_12_10_22_37_51 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'akshay-mac-IPAddress_2025-12-10_22-37-51'
  properties: {
    startIpAddress: '84.1.209.172'
    endIpAddress: '84.1.209.172'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_akshay_mac_retry 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'akshay-mac-retry'
  properties: {
    startIpAddress: '94.27.192.159'
    endIpAddress: '94.27.192.159'
  }
}

resource flexibleServers_socialeconpsy_postgres_db_name_AllowAllAzureServicesAndResourcesWithinAzureIps_2025_12_10_22_42_29 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-01-01-preview' = {
  parent: flexibleServers_socialeconpsy_postgres_db_name_resource
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps_2025-12-10_22-42-29'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}
