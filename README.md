# Microsoft Services SOW AI (msft-sow-ai)

Agentic system on Azure that accelerates Microsoft Services deal velocity by generating
**SOWs**, **Budgetary Estimates (BE)**, **Work Breakdown Structures (WBS)**, and supporting
**collateral** — and, most importantly, generating documents that pass **SQA** review.

Built on lessons learned from the [DOI ROI→FAD MVP](../doi-mvp): durable orchestration,
strict pydantic contracts, citation-grounded generation, template-profile enforcement,
and golden-set evaluation. Re-platformed on **Microsoft Foundry Agents** for faster iteration.

---

## Why this exists

Today, MS Services deals are slowed by:

1. **Manual document authoring** — every SOW is rebuilt from scratch.
2. **Inconsistent BE / WBS** — estimators work from spreadsheets that drift.
3. **SQA bottleneck** — one reviewer reliably blocks deals on style / completeness / risk
   issues that are *deterministic and learnable*.

This system encodes the SQA rubric as a **first-class agent** that runs *before* a human
reviewer ever sees the doc.

---

## Architecture (one paragraph)

A Foundry-hosted multi-agent pipeline. An **Intake Agent** captures the opportunity brief.
A **Solution Architect Agent** drafts the technical approach grounded in past won deals.
Specialist agents draft the **SOW**, **BE**, **WBS**, and **Collateral** in parallel.
An **SQA Gatekeeper Agent** runs the rubric (deterministic checks + LLM critique trained on
historical rejections) and either passes the bundle or returns redlines to the drafters.
Loops until clean, then hands off to a human approver. All artifacts are versioned in
Blob; state lives in Cosmos; grounding corpus lives in AI Search.

See [`docs/architecture.md`](docs/architecture.md) for diagrams and detail.

---

## Repository layout

```
msft-sow-ai/
├── docs/                      Architecture, agent specs, SQA rubric design
├── infra/bicep/               IaC: Foundry, Cosmos, Storage, AI Search, Key Vault
├── src/
│   ├── agents/                Foundry agent definitions (yaml + prompts)
│   ├── orchestrator/          Workflow that wires agents together
│   ├── sqa/                   Gatekeeper rubric engine (deterministic + LLM checks)
│   └── shared/                Pydantic contracts, repositories, renderers
├── templates/                 ← DROP YOUR MS TEMPLATES HERE
│   ├── sow/
│   ├── budgetary_estimate/
│   ├── wbs/
│   └── collateral/
├── corpus/                    Grounding sources (past won deals, rate cards, clauses)
├── sqa/
│   ├── rubrics/               Encoded rules the gatekeeper enforces
│   └── rejection_samples/     ← DROP HISTORICAL SQA REDLINES / REJECTIONS HERE
├── tests/                     Golden-set evaluation harness
└── scripts/                   Deploy, eval, ingest helpers
```

---

## Action items for you (the human)

The system is scaffolded. To make it real, drop content into these folders:

| Folder | What to put there |
|---|---|
| `templates/sow/` | Canonical MS Services SOW DOCX template(s) |
| `templates/budgetary_estimate/` | BE Excel template(s) |
| `templates/wbs/` | WBS template(s) — Excel or MS Project |
| `templates/collateral/` | Slide / one-pager templates |
| `corpus/won_deals/` | 5–20 past SOWs that *did* pass SQA (sanitized) |
| `corpus/rate_cards/` | Current role rate cards |
| `corpus/reusable_clauses/` | Approved standard clauses (assumptions, T&Cs, etc.) |
| `sqa/rejection_samples/` | Past SQA redlines / rejection emails — **highest leverage data** |

Once a few of those are in place, run `scripts/ingest.ps1` to push them into AI Search and
Cosmos as the grounding corpus.

---

## Azure target environment

| Setting | Value |
|---|---|
| Subscription | `MCAPS-Hybrid-REQ-144312-2026-matthewdwilson` |
| Subscription ID | `7ea5743b-273e-42fd-b794-fb7291e76d74` |
| Tenant | Microsoft Non-Production (`fdpo.onmicrosoft.com`) |
| Default region | `eastus2` (override in `infra/bicep/parameters/dev.bicepparam`) |
| Role required | Owner (you have it) |

---

## DOI patterns being reused

- **Strict pydantic contracts** with section-order validators (`src/shared/contracts.py`)
- **Citation contract** — every claim in every artifact must cite a corpus source
- **Template-profile enforcement** — output DOCX must match the customer's template
  styles/sections exactly (not just look similar)
- **Golden-set evaluation** — a small set of "known good" deals scored automatically
- **Modular Bicep** — one module per service, single `main.bicep` entry point
- **Cosmos as source of truth, AI Search as the retrieval index**

## DOI patterns being dropped / replaced

- **Durable Functions orchestrator** → **Foundry Agent workflow** (faster to iterate,
  managed runtime, built-in tracing)
- **Custom chunking pipeline** → **Foundry built-in knowledge index** for the corpus
- **Local dev frontend (Vite)** → **Foundry Playground** for early UX; revisit a custom
  UI only after the agent loop is dialed in

---

## Status

Scaffold only. No agents wired yet. Next milestones:

1. You drop templates + a few rejection samples.
2. We define the SQA rubric (`sqa/rubrics/v1.yaml`) from those samples.
3. We stand up the Foundry project + first two agents (Intake, SOW Drafter).
4. Add SQA Gatekeeper and close the loop.
5. Add BE, WBS, Collateral specialists.
