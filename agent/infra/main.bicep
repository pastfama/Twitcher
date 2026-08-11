// Twitcher Analytics Agent Infrastructure
// Deploys Azure resources for the hosted agent

param location string = resourceGroup().location
param agentName string = 'twagent'

// App Service Plan - use valid SKU
resource appPlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: '${agentName}-plan'
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    capacity: 1
  }
  kind: 'linux'
}

// Storage Account - must be 3-24 chars, lowercase only
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${agentName}stor${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

// PostgreSQL Database - use valid SKU and correct property structure
resource dbServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: '${agentName}-db'
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '14'
    storage: {
      storageSizeGB: 32
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    administratorLogin: 'azureuser'
    administratorLoginPassword: 'ChangeMe123!'
  }
}

resource dbDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: dbServer
  name: 'twitcher'
  properties: {}
}

// Key Vault for secrets
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${agentName}-kv'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

// Application Insights for monitoring
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${agentName}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Outputs
output agentEndpoint string = 'https://${appPlan.name}.azurewebsites.net'
output storageAccountName string = storage.name
output dbServerName string = dbServer.name
output dbDatabaseName string = dbDatabase.name
output keyVaultUri string = keyVault.properties.vaultUri
output appInsightsConnectionString string = appInsights.properties.ConnectionString