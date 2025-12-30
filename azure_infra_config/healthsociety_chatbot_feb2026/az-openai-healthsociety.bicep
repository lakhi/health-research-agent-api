param accounts_az_openai_healthsociety_name string = 'az-openai-healthsociety'

resource accounts_az_openai_healthsociety_name_resource 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accounts_az_openai_healthsociety_name
  location: 'swedencentral'
  tags: {
    Kostenstelle: 'FG473001'
    Umgebung: 'Dev'
    'Verantwortliche*r': 'Akshay'
  }
  sku: {
    name: 'S0'
  }
  kind: 'OpenAI'
  properties: {
    apiProperties: {}
    customSubDomainName: accounts_az_openai_healthsociety_name
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    allowProjectManagement: false
    publicNetworkAccess: 'Enabled'
  }
}

resource accounts_az_openai_healthsociety_name_Default 'Microsoft.CognitiveServices/accounts/defenderForAISettings@2025-06-01' = {
  parent: accounts_az_openai_healthsociety_name_resource
  name: 'Default'
  properties: {
    state: 'Disabled'
  }
}

resource accounts_az_openai_healthsociety_name_embedding_large_dev_healthsoc 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: accounts_az_openai_healthsociety_name_resource
  name: 'embedding-large-dev-healthsoc'
  sku: {
    name: 'Standard'
    capacity: 350
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    versionUpgradeOption: 'NoAutoUpgrade'
    currentCapacity: 350
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource accounts_az_openai_healthsociety_name_gpt_41_dev_healthsoc 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: accounts_az_openai_healthsociety_name_resource
  name: 'gpt-41-dev-healthsoc'
  sku: {
    name: 'DataZoneStandard'
    capacity: 200
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1'
      version: '2025-04-14'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    currentCapacity: 200
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource accounts_az_openai_healthsociety_name_Microsoft_Default 'Microsoft.CognitiveServices/accounts/raiPolicies@2025-06-01' = {
  parent: accounts_az_openai_healthsociety_name_resource
  name: 'Microsoft.Default'
  properties: {
    mode: 'Blocking'
    contentFilters: [
      {
        name: 'Hate'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Hate'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Sexual'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Sexual'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Violence'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Violence'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Selfharm'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Selfharm'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
    ]
  }
}

resource accounts_az_openai_healthsociety_name_Microsoft_DefaultV2 'Microsoft.CognitiveServices/accounts/raiPolicies@2025-06-01' = {
  parent: accounts_az_openai_healthsociety_name_resource
  name: 'Microsoft.DefaultV2'
  properties: {
    mode: 'Blocking'
    contentFilters: [
      {
        name: 'Hate'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Hate'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Sexual'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Sexual'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Violence'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Violence'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Selfharm'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Selfharm'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Jailbreak'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'Protected Material Text'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'Protected Material Code'
        blocking: false
        enabled: true
        source: 'Completion'
      }
    ]
  }
}
