// Static Web App Standard tier — hosts Next.js UX with built-in Entra auth.
// Repo wiring (githubActionWorkflowName etc) is intentionally left to azd / manual,
// to avoid coupling Bicep to a specific deployment toolchain.

param name string
param location string
param tags object = {}

@description('Linked Function App resource ID for SWA bring-your-own backend.')
param linkedBackendResourceId string = ''

@description('Region for the SWA Standard SKU. Standard supports a limited set of regions.')
param skuLocation string = location

resource swa 'Microsoft.Web/staticSites@2024-04-01' = {
  name: name
  location: skuLocation
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    allowConfigFileUpdates: true
    enterpriseGradeCdnStatus: 'Disabled'
    stagingEnvironmentPolicy: 'Enabled'
  }
}

// Bring-your-own backend wiring (links the SWA to the Function App).
resource backendLink 'Microsoft.Web/staticSites/linkedBackends@2024-04-01' = if (!empty(linkedBackendResourceId)) {
  parent: swa
  name: 'api'
  properties: {
    backendResourceId: linkedBackendResourceId
    region: location
  }
}

output name string = swa.name
output id string = swa.id
output defaultHostname string = swa.properties.defaultHostname
