param name string
param location string
param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      { locationName: location, failoverPriority: 0, isZoneRedundant: false }
    ]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    disableLocalAuth: true
    capabilities: []
    publicNetworkAccess: 'Enabled'
  }
}

resource db 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'sowai'
  properties: {
    resource: { id: 'sowai' }
    options: { autoscaleSettings: { maxThroughput: 4000 } }
  }
}

var containers = [
  { id: 'opportunities', pk: '/oppId' }
  { id: 'runs', pk: '/oppId' }
  { id: 'sqa_findings', pk: '/oppId' }
  { id: 'rubric_versions', pk: '/version' }
]

resource cont 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for c in containers: {
  parent: db
  name: c.id
  properties: {
    resource: {
      id: c.id
      partitionKey: { paths: [ c.pk ], kind: 'Hash' }
    }
  }
}]

output name string = cosmos.name
output id string = cosmos.id
