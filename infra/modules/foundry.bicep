param location string = resourceGroup().location
param baseName string = 'maf'
@description('Name for the default model deployment in the Azure AI Services account.')
param modelDeploymentName string = 'gpt-4o'
@description('Model name deployed for default agent usage.')
param modelName string = 'gpt-4o'
@description('Model version applied to the deployment.')
param modelVersion string = '2024-11-20'
@description('Model format for the deployment payload.')
param modelFormat string = 'OpenAI'
@description('SKU name for the deployed model.')
param modelSkuName string = 'Standard'
@description('Capacity value for the deployed model SKU.')
@minValue(1)
param modelSkuCapacity int = 80

// Using resource group ID and subscription ID for deterministic uniqueness
var uniqueSuffix = uniqueString(resourceGroup().id, subscription().id)
var accountName = toLower('${baseName}${uniqueSuffix}aif')
var subDomain   = toLower('${baseName}${uniqueSuffix}sub')
var projectName = toLower('${baseName}${uniqueSuffix}proj')

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'   // 👈 required at top-level
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
    customSubDomainName: subDomain   // 👈 must be globally unique
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  name: modelDeploymentName
  parent: account
  sku: {
    name: modelSkuName
    capacity: modelSkuCapacity
  }
  properties: {
    model: {
      name: modelName
      version: modelVersion
      format: modelFormat
    }
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

resource projectConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  name: 'aiservices'
  parent: project
  properties: {
    category: 'AIServices'
    target: 'https://${subDomain}.services.ai.azure.com'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: account.id
      Location: location
    }
  }
}

output projectEndpoints object = project.properties.endpoints
output projectEndpoint string = 'https://${subDomain}.services.ai.azure.com/api/projects/${projectName}'
output accountName string = accountName
output projectName string = projectName
output subDomain string = subDomain
output defaultModelDeployment string = modelDeployment.name
