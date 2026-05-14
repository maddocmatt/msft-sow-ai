// Data-plane RBAC for the human operator (and optional principals).
// Cosmos data-plane uses its own SQL role assignment (not standard RBAC).

@description('Object ID of the principal to grant data-plane access (user or SP).')
param principalId string

@description('Principal type for ARM role assignments.')
@allowed([ 'User', 'ServicePrincipal', 'Group' ])
param principalType string = 'User'

param storageAccountName string
param searchServiceName string
param foundryAccountName string
param cosmosAccountName string

// --- Built-in role IDs ---
var roleStorageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var roleSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var roleSearchServiceContributor   = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var roleCognitiveServicesUser      = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var roleAzureAIDeveloper           = '64702f94-c441-49e6-a78b-ef80e0188fee'

resource sa 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}
resource srch 'Microsoft.Search/searchServices@2024-03-01-preview' existing = {
  name: searchServiceName
}
resource ai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource raStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sa
  name: guid(sa.id, principalId, roleStorageBlobDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageBlobDataContributor)
    principalId: principalId
    principalType: principalType
  }
}

resource raSearchData 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: srch
  name: guid(srch.id, principalId, roleSearchIndexDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataContributor)
    principalId: principalId
    principalType: principalType
  }
}

resource raSearchSvc 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: srch
  name: guid(srch.id, principalId, roleSearchServiceContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchServiceContributor)
    principalId: principalId
    principalType: principalType
  }
}

resource raAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: ai
  name: guid(ai.id, principalId, roleCognitiveServicesUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
    principalId: principalId
    principalType: principalType
  }
}

resource raAiDev 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: ai
  name: guid(ai.id, principalId, roleAzureAIDeveloper)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIDeveloper)
    principalId: principalId
    principalType: principalType
  }
}

// Cosmos data-plane: built-in 'Cosmos DB Built-in Data Contributor' (id 00000000-0000-0000-0000-000000000002)
resource raCosmos 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, principalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: principalId
    scope: cosmos.id
  }
}
