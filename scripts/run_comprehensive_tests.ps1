$ErrorActionPreference = "Stop"

Write-Host "Running comprehensive test suite..."
pytest backend/tests -q --maxfail=10

Write-Host "Running lint + type checks..."
ruff check backend
mypy backend --ignore-missing-imports

Write-Host "Running coverage report + targets..."
pytest --cov=backend --cov-report=xml --cov-report=term-missing
python scripts/coverage_targets.py

Write-Host "Comprehensive validation complete."
