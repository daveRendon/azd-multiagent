param location string = resourceGroup().location
param prefix string = toLower('maf${uniqueString(resourceGroup().id)}')
@description('Container image reference for the API service. Overridden by azd during deployment.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
@description('Existing triage agent identifier to configure in the API container app.')
param triageAgentId string = ''

module registry './modules/acr.bicep' = {
  name: 'registry'
  params: {
    location: location
    namePrefix: prefix
  }
}

module foundry './modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    baseName: prefix
  }
}

module container './modules/containerapp.bicep' = {
  name: 'container'
  params: {
    location: location
    namePrefix: prefix
    containerImage: containerImage
    projectEndpoint: foundry.outputs.projectEndpoint
    triageAgentId: triageAgentId
    registryServer: registry.outputs.loginServer
    registryName: registry.outputs.name
  }
}

output apiUrl string = container.outputs.fqdn
output projectEndpoint string = foundry.outputs.projectEndpoint
output projectEndpoints object = foundry.outputs.projectEndpoints
output azureContainerRegistryEndpoint string = registry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
