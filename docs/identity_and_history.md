# Identity & History — design notes

> Added 2026-05-14 in response to: "our tool needs history and would probably
> be identity sensitive if I were to roll this out to my brethren in the
> architect group."

## Identity

Single-tenant Entra ID auth, restricted to the Microsoft tenant. We do **not**
allow personal accounts or external guests at the app layer.

### Auth flow

```
Browser ──▶ Static Web App ──▶ Entra ID ──▶ SWA injects x-ms-client-principal ──▶ Azure Function
```

- **Frontend**: Azure Static Web Apps built-in auth, `aad` provider only,
  `allowedRoles: ["authenticated"]` on every route
- **API**: every Azure Function validates the SWA-injected
  `x-ms-client-principal` header before doing anything
- **Identity claim used**: `oid` (object id) as the canonical user key — not email,
  which can change

### Roles

Stored in Cosmos `users` container, not in tokens (so admins can change them
without re-issuing tokens):

| Role | Capabilities |
|---|---|
| `architect` | Default. CRUD on own opportunities, runs, drafts. |
| `reviewer` | All of architect + read-only across all users' drafts (for peer review). |
| `admin` | All of reviewer + edit rubrics, manage users, view audit log. |

### Server-side authorization — non-negotiable

- Never trust a `userId` from the request body
- Always derive the acting user from the validated principal header
- Cosmos queries always filter by `userId` matching the principal

## History

Every run is preserved forever and fully reproducible.

### Cosmos containers (revised)

| Container | Partition key | Purpose |
|---|---|---|
| `users` | `/oid` | One doc per user; role, display name, preferences |
| `opportunities` | `/userId` | An opportunity is owned by one user |
| `runs` | `/userId` | Each generation attempt; immutable once written |
| `drafts` | `/userId` | Versioned artifact bundles produced by runs |
| `sqa_findings` | `/userId` | Every finding ever emitted; training data |
| `rubric_versions` | `/version` | Versioned rubric snapshots |
| `audit_log` | `/yyyymm` | Every privileged action (rubric edit, role change) |

### What every `runs` document contains

```json
{
  "id": "run_20260514_abc",
  "userId": "<oid>",
  "oppId": "opp_xyz",
  "createdAtUtc": "2026-05-14T13:22:09Z",
  "input": {
    "rawText": "<architect's brain dump>",
    "structuredChoices": { "templateVariant": "agile-capacity-v4", "phases": 4, ... }
  },
  "rubricVersion": "1.0.0",
  "corpusSnapshotId": "snap_2026_05_14",
  "agentSteps": [ { "agent": "normalizer", "promptHash": "...", "output": {...} }, ... ],
  "scoreBreakdown": { "scope": 92, "assumptions": 67, "responsibilities": 88, ... },
  "findings": [ { "ruleId": "...", "severity": "...", ... } ],
  "deliverables": [ { "type": "sow", "blobUri": "...", "version": 1 } ],
  "approvedByUserId": null,
  "approvedAtUtc": null
}
```

### Reproducibility guarantee

A run can be replayed by:
1. Loading the run doc
2. Pinning `rubricVersion` and `corpusSnapshotId`
3. Re-invoking the same agents with the captured input

This matters for: audit, A/B testing rubric changes, debugging "why did this
suddenly start failing".

### "My deals" view

Default frontend page after login:
- All opportunities owned by the current user
- For each: latest run, current score, status (draft / approved / sent)
- Filter / sort by date, score, customer
- Click → opportunity detail with full run history + diff between any two runs

### Sharing (deliberate, not implicit)

Architects can grant **read** access to a peer per-opportunity. Stored in the
opportunity doc as a `sharedWith: ["<oid>", ...]` array. Never share by default.

## Storage & blob ACLs

Blob storage uses managed identity + per-user prefix. The Function-App
managed identity has Storage Blob Data Contributor on the account, but
application code enforces that any URI it returns to a user is under
`{userId}/...`.

```
opportunities/{userId}/{oppId}/intake/...
runs/{userId}/{oppId}/{runId}/{agent}.json
deliverables/{userId}/{oppId}/{version}/...
```

## Audit log

Every `admin` and `reviewer` action that touches data they don't own is
appended to `audit_log` with: `actorOid`, `targetUserId`, `action`,
`resourceId`, `tsUtc`. Admin-only view in the UI.

## Open questions (decide before MVP ship)

1. Do we need **GCC / GCC-High** support? If yes, this rules out some Foundry
   features today and changes the deployment region story significantly.
2. **Data residency** — anything in opportunities/drafts that's customer-confidential
   beyond CUI? If yes, may need to push toward GCC.
3. **Retention** — keep runs forever, or 18-month rolling window with archive
   to cool storage? Default: forever.
