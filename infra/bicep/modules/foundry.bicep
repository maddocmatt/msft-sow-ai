// Microsoft Foundry (AI Foundry) account + project — minimal stub.
// We will expand this once the agent definitions in src/agents/ are finalized.

param name string
param location string
param tags object = {}

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'S0' }
  kind: 'AIServices'
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

output name string = foundry.name
output id string = foundry.id
output endpoint string = foundry.properties.endpoint
