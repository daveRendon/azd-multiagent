param location string
@minLength(3)
param namePrefix string

resource registry 'Microsoft.ContainerRegistry/registries@2023-06-01-preview' = {
  name: toLower('${namePrefix}acr')
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    policies: {
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
  }
}

output loginServer string = registry.properties.loginServer
output id string = registry.id
output name string = registry.name
