// main.bicep — msft-sow-ai
// Foundry-first scaffold. Modules are stubs to be filled in iteratively.
// Validated via `bicep build infra/bicep/main.bicep` in CI.

targetScope = 'resourceGroup'

@description('Short prefix for resource names, e.g. sowai')
@minLength(2)
@maxLength(10)
param prefix string = 'sowai'

@description('Environment short name, e.g. dev, test, prod')
@allowed([ 'dev', 'test', 'prod' ])
param env string = 'dev'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Azure region for Azure AI Search (overrides location). Use to dodge regional capacity issues.')
param searchLocation string = location

@description('Tags applied to every resource.')
param tags object = {
  workload: 'msft-sow-ai'
  env: env
  managedBy: 'bicep'
}

@description('Object ID of the human operator who needs data-plane access. If empty, RBAC step is skipped.')
param operatorObjectId string = ''

@description('Principal type for the operator (User, ServicePrincipal, or Group).')
@allowed([ 'User', 'ServicePrincipal', 'Group' ])
param operatorPrincipalType string = 'User'

var nameSuffix = '${prefix}-${env}-${uniqueString(resourceGroup().id)}'

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: 'st${replace(nameSuffix, '-', '')}'
    location: location
    tags: tags
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    name: 'cosmos-${nameSuffix}'
    location: location
    tags: tags
  }
}

module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    name: 'srch-${nameSuffix}'
    location: searchLocation
    tags: tags
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    name: 'aif-${nameSuffix}'
    location: location
    tags: tags
  }
}

module rbac 'modules/rbac.bicep' = if (!empty(operatorObjectId)) {
  name: 'rbac'
  params: {
    principalId: operatorObjectId
    principalType: operatorPrincipalType
    storageAccountName: storage.outputs.name
    searchServiceName: search.outputs.name
    foundryAccountName: foundry.outputs.name
    cosmosAccountName: cosmos.outputs.name
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    name: 'appi-${nameSuffix}'
    location: location
    tags: tags
  }
}

module functionApp 'modules/functionapp.bicep' = {
  name: 'functionApp'
  params: {
    name: 'func-${nameSuffix}'
    location: location
    tags: tags
    storageAccountName: 'stf${take(replace(nameSuffix, '-', ''), 21)}'
    appInsightsConnectionString: monitoring.outputs.connectionString
  }
}

// Grant the Function App's MI data-plane access to Storage/Search/Foundry/Cosmos.
module functionRbac 'modules/rbac.bicep' = {
  name: 'functionRbac'
  params: {
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
    storageAccountName: storage.outputs.name
    searchServiceName: search.outputs.name
    foundryAccountName: foundry.outputs.name
    cosmosAccountName: cosmos.outputs.name
  }
}

module swa 'modules/swa.bicep' = {
  name: 'swa'
  params: {
    name: 'swa-${nameSuffix}'
    location: location
    tags: tags
    linkedBackendResourceId: functionApp.outputs.id
  }
}

output storageAccountName string = storage.outputs.name
output cosmosAccountName string = cosmos.outputs.name
output searchServiceName string = search.outputs.name
output foundryAccountName string = foundry.outputs.name
output foundryEndpoint string = foundry.outputs.endpoint
output functionAppName string = functionApp.outputs.name
output functionAppHostname string = functionApp.outputs.defaultHostName
output staticWebAppName string = swa.outputs.name
output staticWebAppHostname string = swa.outputs.defaultHostname
output appInsightsName string = monitoring.outputs.name
