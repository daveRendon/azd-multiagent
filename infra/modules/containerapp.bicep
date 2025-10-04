param location string
param namePrefix string
@description('Container image reference. Overridden by azd during deployment.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param projectEndpoint string
@description('Agent identifier used by the API to route triage requests.')
param triageAgentId string = ''
@description('Service name tag used by azd to discover the container app during deploy.')
param serviceName string = 'api'
@description('Azure Container Registry login server.')
param registryServer string
@description('Azure Container Registry name used for role assignment.')
param registryName string

resource registry 'Microsoft.ContainerRegistry/registries@2023-06-01-preview' existing = {
  name: registryName
}

resource containerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2018-11-30' = {
  name: '${namePrefix}-acr-id'
  location: location
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {}
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-api'
  location: location
  identity: {
    type: 'SystemAssigned,UserAssigned'
    userAssignedIdentities: {
      '${containerIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullRole
  ]
  tags: {
    'azd-service-name': serviceName
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      registries: [
        {
          server: registryServer
          identity: containerIdentity.id
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          env: concat([
            { name: 'AZURE_CLIENT_ID', value: containerIdentity.properties.clientId }
            { name: 'AIFOUNDRY_PROJECT_ENDPOINT', value: projectEndpoint }
          ], empty(trim(triageAgentId)) ? [] : [
            {
              name: 'TRIAGE_AGENT_ID'
              value: triageAgentId
            }
          ])
        }
      ]
    }
  }
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, containerIdentity.id, 'acrpull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: containerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
