# Security policy

## Reporting

Email the repo owner directly. Do **not** open public issues for security findings.

## Data hygiene

This repo will eventually hold sanitized customer data (SOW samples, SQA rejection
emails). Before committing **anything** under `corpus/`, `sqa/rejection_samples/`,
or `templates/`:

- Remove customer names, replace with `[CUSTOMER]`
- Remove deal $$ values, replace with `[DOLLARS]`
- Remove individuals' names / emails, replace with `[PERSON]` / `[EMAIL]`
- Remove subscription IDs, tenant IDs, resource names that aren't this project's
- Remove anything covered by NDA you cannot scrub

`gitleaks` runs in CI and as a pre-commit hook to catch obvious credential leaks,
but it cannot detect customer PII. That's on you.

## Tooling

- `bandit` — static security analysis on `src/`
- `pip-audit` — dependency vulnerability scan
- `gitleaks` — secret scanning, pre-commit + CI
- `mypy --strict` — type safety
- `ruff` — lint with security rules (`S`)

All of the above run in CI on every PR.
