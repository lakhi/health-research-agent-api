param accounts_az_openai_nex_name string = 'az-openai-nex'

resource accounts_az_openai_nex_name_resource 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accounts_az_openai_nex_name
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
    customSubDomainName: accounts_az_openai_nex_name
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
  }
}

resource accounts_az_openai_nex_content_filter 'Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01' = {
  parent: accounts_az_openai_nex_name_resource
  name: 'nex-content-filter'
  properties: {
    mode: 'Blocking'
    basePolicyName: 'Microsoft.DefaultV2'
    contentFilters: [
      {
        name: 'hate'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'hate'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'sexual'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'sexual'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'violence'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'violence'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'selfharm'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'selfharm'
        severityThreshold: 'Medium'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'jailbreak'
        blocking: true
        enabled: true
        source: 'Prompt'
      }
      {
        name: 'protected_material_text'
        blocking: true
        enabled: true
        source: 'Completion'
      }
      {
        name: 'protected_material_code'
        blocking: false
        enabled: true
        source: 'Completion'
      }
    ]
  }
}

resource accounts_az_openai_nex_embedding_deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: accounts_az_openai_nex_name_resource
  name: 'embedding-large-nex'
  sku: {
    name: 'DataZoneStandard'
    capacity: 350
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    currentCapacity: 350
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [
    accounts_az_openai_nex_content_filter
  ]
}

resource accounts_az_openai_nex_gpt_deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: accounts_az_openai_nex_name_resource
  name: 'gpt-41-nex'
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
    versionUpgradeOption: 'NoAutoUpgrade'
    currentCapacity: 200
    raiPolicyName: 'nex-content-filter'
  }
  dependsOn: [
    accounts_az_openai_nex_embedding_deployment
    accounts_az_openai_nex_content_filter
  ]
}
