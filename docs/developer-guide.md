# Developer Guide

## Local Setup

1. Install Python 3.11+.
2. Install dependencies:
   - `pip install -r requirements-dev.txt`
3. Start backend:
   - `uvicorn backend.app.main:app --reload --port 8000`
4. Start frontend:
   - `cd frontend && npm ci && npm run dev`

## Coding Standards

- Use `ruff` for linting and formatting.
- Use type annotations for all new public interfaces.
- Keep modules cohesive and test each feature slice.

## Testing Guidelines

- Unit tests: `pytest backend/tests -q`.
- Coverage report: `pytest --cov=backend --cov-report=xml`.
- Coverage threshold check: `python scripts/coverage_targets.py`.
- Property tests are marked with `@pytest.mark.property_test`.

## Contribution Workflow

1. Implement feature with tests.
2. Run `ruff check backend` and `mypy backend --ignore-missing-imports`.
3. Ensure CI passes.
4. Open pull request against `main` or `develop`.
