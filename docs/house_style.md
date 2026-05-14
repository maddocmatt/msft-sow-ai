# House Style Guide — derived from approved MS US Federal SOW templates

> Source: `templates/_profiles/_language.json`, mined from 9 approved templates
> (Mar/Apr 2026 versions). All evidence counts come from that file.

This is the style every drafter agent must hit. The SQA Gatekeeper enforces it.
The point is to leave SQA reviewers with **nothing to argue about** by matching
the patterns their own approved templates establish.

---

## Voice

| Rule | Evidence | Pattern |
|---|---|---|
| **Subject = Microsoft** in scope/approach | "Microsoft will assist…" / "Microsoft will provide…" appear ~unanimously | `Microsoft will [verb] [thing]` |
| **Subject = Customer** in customer responsibilities | "The Customer will…" / "Provide access to…" | `The Customer will [verb] [thing]` |
| **NEVER subject = the system** in scope | This is the PLURRI pattern: "Your scope describes what the tool will do once implemented — it doesn't describe what MS will be doing to implement." | ❌ "The platform will ingest data" → ✅ "Microsoft will design and build the ingestion pipeline" |

## Canonical scope verbs (use ≥ 3)

Frequency in approved templates:

| Verb | Count | Use for |
|---|---|---|
| design | 33 | Architectures, patterns, frameworks |
| review | 26 | Existing artifacts, code, processes |
| create | 20 | New artifacts |
| perform | 10 | Assessments, validations |
| deploy | 8 | Environments, code |
| deliver | 7 | Final artifacts to customer |
| document | 7 | Anything that needs writing down |
| assess | 7 | Current state, posture |
| build | 5 | Solution components |

**Notably underused:** `implement` (1). Prefer `build` + `deploy` over `implement`.

## Hedges — these ARE allowed

Counterintuitively, these appear constantly in approved templates and should NOT be flagged:

| Hedge | Count | Why allowed |
|---|---|---|
| may | 171 | Standard contractual modal |
| should | 82 | Recommendation language |
| could | 61 | Conditional statements |
| various / some | 18 / 17 | Reasonable in assumptions |
| as needed | 17 | Standard ops phrasing |
| approximately | 13 | Standard estimate hedge |

## Hedges — these are BLOCKERS

| Token | Count in approved | Why banned |
|---|---|---|
| TBD | 1 | Signals incomplete drafting |
| to be determined | 1 | Same |
| Whisper / Whisper Number | 0 | Retired from FedSQA taxonomy |
| N-1 / N-2 / L0 | 0 | Non-canonical approval levels |

## Required placeholders to FILL (none should remain)

The templates carry these markers everywhere — the drafter's job is to resolve every one:

| Marker | Count | Replace with |
|---|---|---|
| `<Customer Name>` | 437 | Customer legal name |
| `<Microsoft OR Partner name>` | 112 | "Microsoft" or partner name |
| `<Project Name>` | 29 | Agreed project name |
| `[insert WO number]` etc. | 5+ | Concrete value |
| `[Template Guidance: …]` | 3+ | Delete or resolve |

## Canonical section openings

Use these sentence stems verbatim or with minimal substitution:

**Scope section:**
> "The objective of this engagement is to [outcome]."
> "Microsoft will assist the Customer as directed by the Customer Project Manager with the following areas."

**Out-of-scope section:**
> "Any area not explicitly included in the Areas in scope section is out of scope for Microsoft during this engagement. Areas out of scope for this engagement include but are not limited to those items listed in the following table."

**Approach section:**
> "This section outlines the work and activities required to assist the customer in accomplishing their objectives set forth in this SOW."

**Customer responsibilities:**
> "In addition to Customer activities defined elsewhere in the SOW, the Customer will:"
> "Provide information." (with sub-text)
> "Provide access to people and resources."
> "Provide access to systems."

## Standard assumption boilerplate (always include)

| Assumption | Canonical text |
|---|---|
| Workday | "The standard workday for the Microsoft project team is between 8 AM and 5 PM, Monday through Friday, local time where the team is working." |
| Remote work | "The Microsoft project team may perform services remotely." |
| Funding cap | "Microsoft will not provide services beyond the currently funded amount as set forth in the Work Order." |
| Staffing changes | "If necessary, Microsoft will make staffing changes. These may include, but are not limited to, the number of resources, individuals, and project roles." |
| Resource access | "All resources will have the appropriate level of security access required to complete project-related efforts or customer will submit individuals for the appropriate level of security access." |

## Document-type discipline

Templates declare type explicitly. Every draft must too.

| Type | When | Approval |
|---|---|---|
| **ROM** (Rough Order of Magnitude) | Comparison-based price using a similar past project | Per FedSQA Battle Card |
| **BE** (Budgetary Estimate) | Estimate built from customer requirements; non-binding | L3 default; exceptions per Battle Card |
| **SOW** | Binding scope + price | Full ESAP review |

A SOW is not a BE. A BE is not a ROM. Mislabeling is an instant SQA reject.

## Pricing constructs

- **Standard FFP**: no special evidence needed
- **Non-Standard FFP**: requires a customer email accepting the construct, uploaded to Compass; SOW must reference the Compass artifact ID
- **T&M**: per-template (Staff Aug T&M, Sprint Zero, Agile Capacity templates)
- **Capacity-based agile**: use the "Agile Capacity SOW" template specifically; assumes the canonical agile delivery model

## Anti-pattern catalog (mined from real disputes)

| Anti-pattern | Why it triggers SQA | Fix |
|---|---|---|
| Scope describes tool capabilities | "describes what the tool will do once implemented" | Rewrite as MS verbs |
| Generic statement | "Again this is a generic statement" | Add named workload, deliverable, or measurable outcome |
| Document mislabeled (BE called SOW or vice versa) | "Correct - this is a SOW - not a BE" | Declare type in title + footer |
| Whisper number / N-1 references | Retired terminology | Use BE/ROM and L1/L2/L3 |
| Non-standard FFP without customer email | Out of compliance with Compass workflow | Reference Compass artifact ID |
