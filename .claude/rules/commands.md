# Command Execution Rules

This project uses `uv` for Python environment and dependency management.

## Golden Rule

**ALL Python commands MUST be run via `uv run`.**

## Prohibited Patterns

NEVER use any of the following:

- `source .venv/bin/activate` — uv handles the environment
- `.venv/bin/python` — never call venv python directly
- `python -m pytest` — always use `uv run pytest`
- `python3 -m pytest` — always use `uv run pytest`
- bare `pytest` — always use `uv run pytest`
- bare `ruff` — always use `uv run ruff`

## Test Commands

```bash
# Run all tests
uv run pytest -v

# Run tests for a specific service
uv run pytest tests/services/github/ -v
uv run pytest tests/services/ticktick/ -v

# Run a specific test file
uv run pytest tests/services/github/test_domain.py -v

# Run a specific test class
uv run pytest tests/services/github/test_domain.py::TestGitHubIssue -v

# Run a specific test function
uv run pytest tests/services/github/test_domain.py::TestGitHubIssue::test_is_overdue -v
```

## Lint & Format Commands

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix lint errors
uv run ruff check --fix .

# Check formatting
uv run ruff format --check .

# Auto-format
uv run ruff format .
```

## Dependency Management

```bash
# Add a production dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Sync environment with lockfile
uv sync
```

## Project Structure

- Tests mirror the source tree: `bot/services/github/` → `tests/services/github/`
- pytest config is in `pyproject.toml` under `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` is set — no `@pytest.mark.asyncio` decorator needed
