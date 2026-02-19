# Command Execution Rules & Lint Setup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish `.claude/rules/` with uv-based command execution rules so Claude Code never uses wrong Python commands, and add ruff for linting/formatting.

**Architecture:** Single `.claude/rules/commands.md` file defines all command conventions. ruff added as dev dependency with minimal config in pyproject.toml. AGENTS.md deleted. settings.local.json cleaned up.

**Tech Stack:** uv, pytest, ruff

---

### Task 1: Add ruff to dev dependencies

**Files:**
- Modify: `pyproject.toml:16-24`

**Step 1: Add ruff and ruff config to pyproject.toml**

Edit `pyproject.toml` — add `ruff` to dev deps and add `[tool.ruff]` section:

```toml
[dependency-groups]
dev = [
    "aioresponses>=0.7.8",
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "ruff>=0.11.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py313"
line-length = 88
```

**Step 2: Install the new dependency**

Run: `uv sync`
Expected: ruff is installed, uv.lock is updated

**Step 3: Verify ruff works**

Run: `uv run ruff check .`
Expected: ruff runs (may show warnings, that's fine)

Run: `uv run ruff format --check .`
Expected: ruff format runs (may show files that need formatting, that's fine)

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add ruff to dev dependencies"
```

---

### Task 2: Create `.claude/rules/commands.md`

**Files:**
- Create: `.claude/rules/commands.md`

**Step 1: Create the rules file**

Create `.claude/rules/commands.md` with this exact content:

```markdown
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
```

**Step 2: Commit**

```bash
git add .claude/rules/commands.md
git commit -m "chore: add command execution rules for Claude Code"
```

---

### Task 3: Delete AGENTS.md and clean up settings

**Files:**
- Delete: `AGENTS.md`
- Modify: `.claude/settings.local.json`

**Step 1: Delete AGENTS.md**

```bash
git rm AGENTS.md
```

**Step 2: Clean up `.claude/settings.local.json`**

Replace the full content with:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run pytest:*)",
      "Bash(uv run ruff:*)",
      "Bash(uv run python:*)",
      "Bash(uv sync:*)",
      "Bash(uv add:*)",
      "Bash(ls:*)",
      "Bash(gh issue view:*)",
      "Bash(gh issue list:*)"
    ]
  }
}
```

Removed:
- `Bash(python -m pytest:*)` — prohibited
- `Bash(python3 -m pytest:*)` — prohibited
- `Bash(./.venv/bin/python -m pytest ...)` — prohibited
- `Bash(git -C ... status/diff/log)` — unnecessary, git works without -C

Added:
- `Bash(uv run ruff:*)` — for lint/format
- `Bash(uv sync:*)` — for dependency sync
- `Bash(uv add:*)` — for adding dependencies

**Step 3: Commit**

```bash
git add AGENTS.md .claude/settings.local.json
git commit -m "chore: remove AGENTS.md, clean up settings permissions"
```

---

### Task 4: Verify everything works end-to-end

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run ruff check**

Run: `uv run ruff check .`
Expected: ruff runs successfully

**Step 3: Run ruff format check**

Run: `uv run ruff format --check .`
Expected: ruff runs successfully

**Step 4: Fix any ruff issues if needed**

If ruff reports fixable issues:
Run: `uv run ruff check --fix .`
Run: `uv run ruff format .`

Then commit fixes:
```bash
git add -A
git commit -m "style: apply ruff formatting and lint fixes"
```
