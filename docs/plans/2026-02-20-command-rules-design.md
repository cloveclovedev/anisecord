# Command Execution Rules & Lint Setup Design

Date: 2026-02-20

## Problem

Claude Code frequently uses wrong commands when running tests and other Python tools in this uv-managed project. It tries `source .venv/bin/activate`, `.venv/bin/python -m pytest`, `python -m pytest`, etc. instead of the correct `uv run` approach.

## Solution

### 1. `.claude/rules/commands.md`

Establish a single source of truth for how to execute commands in this project:

- **Rule**: All Python commands MUST use `uv run` prefix. No exceptions.
- **Prohibited**: `source`, `.venv/bin/python`, `python -m`, `python3 -m`, direct `pytest`, direct `ruff`
- **Test commands**: `uv run pytest` with examples (all, file, class, function)
- **Lint commands**: `uv run ruff check` and `uv run ruff format`
- **Dependency management**: `uv add`, `uv add --dev`

### 2. `pyproject.toml` changes

Add ruff as dev dependency and minimal config:

```toml
[dependency-groups]
dev = [
    "aioresponses>=0.7.8",
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "ruff>=0.11.0",
]

[tool.ruff]
target-version = "py313"
line-length = 88
```

### 3. Delete `AGENTS.md`

Its content (test commands) was written during a confused session and contains incorrect patterns. The `.claude/rules/` file replaces it entirely.

### 4. Clean up `.claude/settings.local.json`

Remove permissions for deprecated command patterns (`source`, `.venv/bin/python`) and add `uv run ruff` permission.

## Out of Scope

- CI/CD setup
- Makefile or other task runners
- Advanced ruff rule configuration (can be added later)
