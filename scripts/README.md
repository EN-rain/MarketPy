# Scripts

This directory contains utility scripts for maintaining code quality and preventing common issues.

## check_duplicate_dataclasses.py

Detects duplicate dataclass definitions across the codebase to prevent type drift.

### Purpose

This script scans all Python files in the project and identifies dataclasses with the same name defined in multiple locations. Duplicate dataclass definitions can lead to:

- Type drift between modules
- Maintenance issues when updating data structures
- Import confusion and bugs

### Usage

Run the script from the project root:

```bash
python scripts/check_duplicate_dataclasses.py
```

### Exit Codes

- `0` - No duplicates found (success)
- `1` - Duplicates detected (failure)

### Example Output

When no duplicates are found:
```
Scanning for dataclass definitions in: /path/to/project
Excluding directories: __pycache__, .pytest_cache, node_modules, ...
Found 87 Python files to analyze
Found 34 total dataclass definitions

✓ No duplicate dataclass definitions found!
```

When duplicates are detected:
```
✗ Found 2 duplicate dataclass name(s):

Dataclass 'MarketUpdate' defined in 2 locations:
  - backend/app/models/market.py:43
    Fields: market_id, timestamp, mid, bid, ask, last_trade, orderbook, volume_24h, change_24h_pct
  - backend/paper_trading/live_feed.py:25
    Fields: market_id, timestamp, price

Action required: Remove duplicate definitions and use a single canonical location.
Refer to backend/app/models/market.py for an example of canonical model definitions.
```

### CI Integration

This script is automatically run in CI via GitHub Actions (`.github/workflows/check-duplicates.yml`). The CI build will fail if any duplicate dataclass definitions are detected.

### Configuration

The script excludes certain directories from scanning:
- `__pycache__` - Python bytecode cache
- `.pytest_cache` - Pytest cache
- `.hypothesis` - Hypothesis testing cache
- `.ruff_cache` - Ruff linter cache
- `node_modules` - Node.js dependencies
- `.venv`, `venv` - Virtual environments
- `.git` - Git repository data
- `marketpy.egg-info` - Python package metadata
- `frontend` - Frontend code (TypeScript/JavaScript)

### Best Practices

When the script detects duplicates:

1. **Identify the canonical location**: Choose one location as the single source of truth (typically in `backend/app/models/`)
2. **Update imports**: Change all imports to reference the canonical location
3. **Remove duplicates**: Delete the duplicate definitions
4. **Run tests**: Ensure all tests pass after the changes
5. **Verify**: Run the script again to confirm no duplicates remain

### Example: Fixing Duplicates

If `MarketUpdate` is duplicated:

1. Keep the canonical definition in `backend/app/models/market.py`
2. Update imports in other files:
   ```python
   # Before
   from backend.paper_trading.live_feed import MarketUpdate
   
   # After
   from backend.app.models.market import MarketUpdate
   ```
3. Remove the duplicate definition from `backend/paper_trading/live_feed.py`
4. Run tests: `pytest backend/tests/`
5. Verify: `python scripts/check_duplicate_dataclasses.py`

### Testing

The script has comprehensive unit tests in `backend/tests/test_duplicate_dataclass_checker.py`:

```bash
pytest backend/tests/test_duplicate_dataclass_checker.py -v
```

Tests cover:
- Extracting single and multiple dataclasses
- Detecting duplicates with various patterns
- Handling edge cases (empty dataclasses, default values, etc.)
- Integration test against the actual codebase
