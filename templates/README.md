# Templates — DROP HERE

Subfolders for each artifact type. Put canonical Microsoft Services templates in:

- `sow/` — SOW DOCX
- `budgetary_estimate/` — BE XLSX
- `wbs/` — WBS XLSX or MS Project
- `collateral/` — PPTX / one-pager templates

The SOW Drafter and BE Estimator agents will load these as **template profiles** and
produce outputs that match the exact section structure, styles, and named ranges. This
mirrors the DOI MVP's `fad_template_profile.py` approach — never let the LLM invent the
document skeleton.

Filename convention: `mss-{artifact}-{version}.{ext}` e.g. `mss-sow-2026q1.docx`.
