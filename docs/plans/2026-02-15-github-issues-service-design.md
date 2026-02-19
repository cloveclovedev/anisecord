# GitHub Issues Service Design

**Date:** 2026-02-15
**Issue:** #35 (Epic)
**Status:** Approved

## Overview

A service layer that integrates with the GitHub Issues API to provide issue and milestone data as domain objects. Serves as a data source for the Planning feature (daily plan / weekly plan) alongside the TickTick service.

## Approach: Milestone-Centered Design

GitHub Issues for personal projects typically lack individual due dates. Instead of requiring per-issue due dates or heavy GitHub Projects integration, this service uses **milestones as the temporal axis**:

- **Milestones** = release deadlines (due dates set at milestone level only)
- **Assignee** = filter for "my tasks"
- **Daily plan**: issues in the nearest milestone
- **Weekly plan**: milestone progress overview + all issues

This keeps operational overhead low while providing temporal structure.

## Scope

- Create data access layer at `bot/services/github/`
- Fetch open milestones with their issues across specified repositories
- Fetch milestone-less assigned issues as "Backlog"
- PAT authentication (Phase 1: stored in .env)
- Return domain objects for consumption by the planning feature

## Out of Scope

- `/daily-plan` command (separate ticket)
- Auto-posting to diary channel (separate ticket)
- Multi-user support (Phase 2)
- Write operations to GitHub (creating/closing issues)
- GitHub Projects integration

## Directory Structure

```
bot/services/github/
├── __init__.py
├── domain.py          # Domain models (GitHubIssue, GitHubMilestone)
├── repository.py      # API calls + domain conversion

tests/services/github/
├── __init__.py
├── test_domain.py
├── test_repository.py
```

No `auth.py` needed — PAT is a static token passed via HTTP header, unlike TickTick's OAuth refresh flow.

## Domain Model

```python
@dataclass(frozen=True)
class GitHubMilestone:
    number: int
    title: str
    due_date: Optional[date] = None      # milestone's due_on field
    open_issues: int = 0
    closed_issues: int = 0
    state: str = "open"                   # "open" | "closed"

    @property
    def progress(self) -> float:
        """Completion ratio (0.0 to 1.0)."""
        total = self.open_issues + self.closed_issues
        return self.closed_issues / total if total > 0 else 0.0

    @property
    def is_overdue(self) -> bool:
        """Whether due_date is before today."""
        if self.due_date is None:
            return False
        return self.due_date < date.today()


@dataclass(frozen=True)
class GitHubIssue:
    number: int
    title: str
    repo: str                             # "owner/repo" format
    state: str = "open"                   # "open" | "closed"
    labels: tuple[str, ...] = ()
    milestone: Optional[GitHubMilestone] = None
    url: str = ""                         # HTML link
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### Design Decisions

- `frozen=True` for consistency with existing patterns (DiscordPost, TickTickTask)
- `repo` field needed to identify which repository an issue belongs to across multi-repo queries
- `milestone` is Optional — issues without milestones are treated as "Backlog"
- No priority enum — GitHub labels are free-form strings, kept as a simple tuple
- No `assignee` field — API queries already filter by assignee, so it would be redundant
- Minimal fields — only what the planning feature needs. GitHub API returns dozens of fields per issue; we extract only what's relevant

## Repository

### API Endpoints Used

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/repos/{owner}/{repo}/milestones` | List open milestones |
| GET | `/repos/{owner}/{repo}/issues` | List issues (filtered by milestone or assignee) |

Base URL: `https://api.github.com`
Auth header: `Authorization: Bearer {token}`
Accept header: `application/vnd.github+json`

### Key Methods

```python
class GitHubRepository:
    def __init__(self, token: str, repos: list[str]):
        """
        Args:
            token: Personal Access Token
            repos: ["owner/repo1", "owner/repo2"]
        """
        self._token = token
        self._repos = repos

    async def fetch_milestones(self, repo: str) -> list[GitHubMilestone]:
        """Fetch open milestones for a repo."""
        # GET /repos/{owner}/{repo}/milestones?state=open&sort=due_on

    async def fetch_issues_by_milestone(
        self, repo: str, milestone_number: int
    ) -> list[GitHubIssue]:
        """Fetch open issues for a specific milestone."""
        # GET /repos/{owner}/{repo}/issues?milestone={number}&state=open

    async def fetch_issues_without_milestone(
        self, repo: str
    ) -> list[GitHubIssue]:
        """Fetch open assigned issues without a milestone (Backlog)."""
        # GET /repos/{owner}/{repo}/issues?milestone=none&state=open&assignee={user}

    async def fetch_actionable_issues(self) -> list[GitHubIssue]:
        """Fetch all planning-relevant issues across all configured repos."""
        # 1. For each repo: fetch open milestones
        # 2. For each milestone: fetch its issues
        # 3. For each repo: fetch milestone-less assigned issues
        # 4. Return combined list

    async def _request(
        self, method: str, path: str, params: dict | None = None
    ) -> Any:
        """Make a GitHub API request with pagination support."""
        # Follows Link header 'next' for paginated results
        # No 401 retry needed (PAT doesn't expire like OAuth tokens)
```

### Design Decisions

- No `auth.py` — PAT is static, no refresh/lock mechanism needed (unlike TickTick OAuth)
- Pagination via Link header — GitHub defaults to 30 items/page
- `fetch_actionable_issues` is the main entry point for the planning layer (mirrors TickTick's `fetch_actionable_tasks`)
- Assignee filter only on milestone-less issues — milestone issues show all assignees for progress visibility
- Simple `raise_for_status` on errors — no 401 retry logic needed

## HTTP Client

- **aiohttp** (consistent with TickTick service)
- `aiohttp.ClientTimeout(total=30)` per request

## Environment Variables

```
GITHUB_TOKEN=ghp_xxxxx                    # Fine-grained PAT
GITHUB_REPOS=owner/repo1,owner/repo2      # Comma-separated list
```

## Testing

```
tests/services/github/
├── __init__.py
├── test_domain.py        # Domain model property tests
├── test_repository.py    # API response mock → domain conversion tests
```

### test_domain.py

- `GitHubMilestone.progress`: zero issues, partial, fully complete
- `GitHubMilestone.is_overdue`: no due_date, future date, past date

### test_repository.py

- API response JSON → `GitHubIssue` / `GitHubMilestone` conversion
- Both milestone-bound and milestone-less issues are fetched
- Pagination (Link header with `next` URL)
- Multi-repo aggregation

### Mock Strategy

- `aioresponses` for mocking aiohttp responses (same as TickTick)

## Dependencies

No new dependencies — `aiohttp` and `aioresponses` already added for TickTick service.

## Multi-User Considerations (Phase 2)

Current design accepts `token: str` in the repository constructor. For multi-user:

- Token source becomes swappable (DB, secrets manager, or OAuth)
- Options: encrypted DB storage, AWS Secrets Manager, or GitHub OAuth App flow
- Constructor interface stays the same — only the token provider changes
- Detailed design deferred to Phase 2

## Role in Planning Feature

| Plan Type | TickTick (time-driven) | GitHub Issues (focus-driven) |
|-----------|----------------------|----------------------------|
| Daily | Tasks due today + overdue | Issues in nearest milestone |
| Weekly | Tasks due this week | Milestone progress + all issues |

The two services complement each other: TickTick handles time-bound tasks, GitHub Issues handles development work with release-oriented milestones.
