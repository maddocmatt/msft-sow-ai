# Local quality gate — runs everything CI runs.
# Fail fast on first error.
$ErrorActionPreference = 'Stop'

Write-Host '== ruff lint ==' -ForegroundColor Cyan
ruff check .

Write-Host '== ruff format check ==' -ForegroundColor Cyan
ruff format --check .

Write-Host '== mypy ==' -ForegroundColor Cyan
mypy src

Write-Host '== bandit ==' -ForegroundColor Cyan
bandit -c pyproject.toml -r src

Write-Host '== pytest ==' -ForegroundColor Cyan
pytest

Write-Host '== bicep build ==' -ForegroundColor Cyan
bicep build infra/bicep/main.bicep

Write-Host 'All checks passed.' -ForegroundColor Green
