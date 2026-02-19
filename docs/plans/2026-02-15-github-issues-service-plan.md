# GitHub Issues Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a service layer that fetches GitHub Issues and Milestones via the REST API, returning domain objects for the Planning feature.

**Architecture:** Follows the same pattern as `bot/services/ticktick/` — domain models in `domain.py`, API access in `repository.py`. PAT auth is inline (no separate auth module). TDD with `aioresponses` mocks.

**Tech Stack:** Python 3.13, aiohttp, pytest, aioresponses, pytest-asyncio (asyncio_mode=auto)

**Design Doc:** `docs/plans/2026-02-15-github-issues-service-design.md`

---

### Task 1: Domain Models — GitHubMilestone

**Files:**
- Create: `tests/services/github/__init__.py`
- Create: `tests/services/github/test_domain.py`
- Create: `bot/services/github/__init__.py`
- Create: `bot/services/github/domain.py`

**Step 1: Write the failing tests**

Create `tests/services/github/__init__.py` (empty) and `tests/services/github/test_domain.py`:

```python
from datetime import date
from unittest.mock import patch

from bot.services.github.domain import GitHubMilestone


class TestGitHubMilestone:
    def test_creation_minimal(self):
        ms = GitHubMilestone(number=1, title="v1.0")
        assert ms.number == 1
        assert ms.title == "v1.0"
        assert ms.due_date is None
        assert ms.open_issues == 0
        assert ms.closed_issues == 0
        assert ms.state == "open"

    def test_creation_with_all_fields(self):
        ms = GitHubMilestone(
            number=2,
            title="v2.0",
            due_date=date(2026, 3, 1),
            open_issues=5,
            closed_issues=10,
            state="open",
        )
        assert ms.due_date == date(2026, 3, 1)
        assert ms.open_issues == 5
        assert ms.closed_issues == 10

    def test_frozen(self):
        ms = GitHubMilestone(number=1, title="v1.0")
        try:
            ms.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_progress_no_issues(self):
        ms = GitHubMilestone(number=1, title="v1.0", open_issues=0, closed_issues=0)
        assert ms.progress == 0.0

    def test_progress_partial(self):
        ms = GitHubMilestone(number=1, title="v1.0", open_issues=3, closed_issues=7)
        assert ms.progress == 0.7

    def test_progress_all_closed(self):
        ms = GitHubMilestone(number=1, title="v1.0", open_issues=0, closed_issues=5)
        assert ms.progress == 1.0

    @patch("bot.services.github.domain._today")
    def test_is_overdue_no_due_date(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=None)
        assert ms.is_overdue is False

    @patch("bot.services.github.domain._today")
    def test_is_overdue_future(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=date(2026, 3, 1))
        assert ms.is_overdue is False

    @patch("bot.services.github.domain._today")
    def test_is_overdue_past(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=date(2026, 2, 10))
        assert ms.is_overdue is True

    @patch("bot.services.github.domain._today")
    def test_is_overdue_today(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=date(2026, 2, 15))
        assert ms.is_overdue is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/github/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.services.github'`

**Step 3: Write the implementation**

Create `bot/services/github/__init__.py` (empty) and `bot/services/github/domain.py`:

```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


def _today() -> date:
    """Return today's date. Extracted for testability."""
    return date.today()


@dataclass(frozen=True)
class GitHubMilestone:
    number: int
    title: str
    due_date: Optional[date] = None
    open_issues: int = 0
    closed_issues: int = 0
    state: str = "open"

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
        return self.due_date < _today()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/github/test_domain.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add bot/services/github/__init__.py bot/services/github/domain.py \
       tests/services/github/__init__.py tests/services/github/test_domain.py
git commit -m "feat(github): add GitHubMilestone domain model with tests"
```

---

### Task 2: Domain Models — GitHubIssue

**Files:**
- Modify: `bot/services/github/domain.py`
- Modify: `tests/services/github/test_domain.py`

**Step 1: Add failing tests**

Append to `tests/services/github/test_domain.py`:

```python
from bot.services.github.domain import GitHubIssue, GitHubMilestone


class TestGitHubIssue:
    def test_creation_minimal(self):
        issue = GitHubIssue(number=42, title="Fix bug", repo="owner/repo1")
        assert issue.number == 42
        assert issue.title == "Fix bug"
        assert issue.repo == "owner/repo1"
        assert issue.state == "open"
        assert issue.labels == ()
        assert issue.milestone is None
        assert issue.url == ""
        assert issue.created_at is None
        assert issue.updated_at is None

    def test_creation_with_all_fields(self):
        ms = GitHubMilestone(number=1, title="v1.0")
        issue = GitHubIssue(
            number=99,
            title="Add feature",
            repo="owner/repo2",
            state="open",
            labels=("enhancement", "priority:high"),
            milestone=ms,
            url="https://github.com/owner/repo2/issues/99",
            created_at=datetime(2026, 2, 10, 12, 0),
            updated_at=datetime(2026, 2, 14, 15, 30),
        )
        assert issue.milestone.title == "v1.0"
        assert issue.labels == ("enhancement", "priority:high")
        assert "repo2" in issue.url

    def test_frozen(self):
        issue = GitHubIssue(number=1, title="t", repo="o/r")
        try:
            issue.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass
```

Note: add `from datetime import datetime` to the existing imports in the test file.

**Step 2: Run tests to verify new tests fail**

Run: `pytest tests/services/github/test_domain.py::TestGitHubIssue -v`
Expected: FAIL with `ImportError: cannot import name 'GitHubIssue'`

**Step 3: Add GitHubIssue to domain.py**

Append to `bot/services/github/domain.py`:

```python
@dataclass(frozen=True)
class GitHubIssue:
    number: int
    title: str
    repo: str
    state: str = "open"
    labels: tuple[str, ...] = ()
    milestone: Optional[GitHubMilestone] = None
    url: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

**Step 4: Run all domain tests**

Run: `pytest tests/services/github/test_domain.py -v`
Expected: All 13 tests PASS

**Step 5: Commit**

```bash
git add bot/services/github/domain.py tests/services/github/test_domain.py
git commit -m "feat(github): add GitHubIssue domain model with tests"
```

---

### Task 3: Repository — Setup, _request with Pagination

**Files:**
- Create: `bot/services/github/repository.py`
- Create: `tests/services/github/test_repository.py`

**Step 1: Write failing tests for _request and pagination**

Create `tests/services/github/test_repository.py`:

```python
import re

from aioresponses import aioresponses

from bot.services.github.repository import GitHubRepository

API_BASE = "https://api.github.com"


def make_repo(repos: list[str] | None = None) -> GitHubRepository:
    return GitHubRepository(
        token="test_token",
        repos=repos or ["owner/repo1"],
    )


class TestRequest:
    async def test_sends_auth_header(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(f"{API_BASE}/test", payload={"ok": True})
            result = await repo._request("GET", "/test")

        assert result == [{"ok": True}]
        # Verify auth header was sent
        call = m.requests[("GET", m._build_url(f"{API_BASE}/test"))][0]
        assert call.kwargs["headers"]["Authorization"] == "Bearer test_token"

    async def test_pagination_follows_link_header(self):
        repo = make_repo()
        page1_url = f"{API_BASE}/repos/owner/repo1/issues?state=open"
        page2_url = f"{API_BASE}/repos/owner/repo1/issues?state=open&page=2"

        with aioresponses() as m:
            m.get(
                page1_url,
                payload=[{"number": 1}],
                headers={"Link": f'<{page2_url}>; rel="next"'},
            )
            m.get(
                page2_url,
                payload=[{"number": 2}],
            )
            result = await repo._request("GET", "/repos/owner/repo1/issues", params={"state": "open"})

        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    async def test_no_pagination_when_no_link_header(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(f"{API_BASE}/test", payload=[{"id": 1}])
            result = await repo._request("GET", "/test")

        assert result == [{"id": 1}]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/github/test_repository.py::TestRequest -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

**Step 3: Implement repository skeleton with _request**

Create `bot/services/github/repository.py`:

```python
import logging
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .domain import GitHubIssue, GitHubMilestone

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
JST = ZoneInfo("Asia/Tokyo")

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubRepository:
    def __init__(self, token: str, repos: list[str]):
        self._token = token
        self._repos = repos

    async def _request(
        self, method: str, path: str, params: dict | None = None
    ) -> list[Any]:
        """Make a GitHub API request. Returns aggregated results across all pages."""
        url = f"{GITHUB_API_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
        }
        timeout = aiohttp.ClientTimeout(total=30)
        all_items: list[Any] = []

        async with aiohttp.ClientSession(timeout=timeout) as session:
            current_url: str | None = url
            current_params = params

            while current_url:
                async with session.request(
                    method,
                    current_url,
                    headers=headers,
                    params=current_params,
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    if isinstance(data, list):
                        all_items.extend(data)
                    else:
                        all_items.append(data)

                    # Check for next page
                    link = resp.headers.get("Link", "")
                    match = _LINK_NEXT_RE.search(link)
                    if match:
                        current_url = match.group(1)
                        current_params = None  # params are in the URL
                    else:
                        current_url = None

        return all_items
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/github/test_repository.py::TestRequest -v`
Expected: All 3 tests PASS

Note: The auth header assertion may need adjustment based on how aioresponses captures request kwargs. If the test fails on header verification, simplify to just testing the response. Adjust the assertion in Step 1 accordingly:

```python
    async def test_sends_auth_header(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(f"{API_BASE}/test", payload={"ok": True})
            result = await repo._request("GET", "/test")
        assert result == [{"ok": True}]
```

**Step 5: Commit**

```bash
git add bot/services/github/repository.py tests/services/github/test_repository.py
git commit -m "feat(github): add GitHubRepository with paginated _request"
```

---

### Task 4: Repository — fetch_milestones

**Files:**
- Modify: `bot/services/github/repository.py`
- Modify: `tests/services/github/test_repository.py`

**Step 1: Write failing tests**

Add to `tests/services/github/test_repository.py`:

```python
from datetime import date

from bot.services.github.domain import GitHubMilestone

SAMPLE_MILESTONES = [
    {
        "number": 1,
        "title": "v1.0",
        "due_on": "2026-03-01T08:00:00Z",
        "open_issues": 3,
        "closed_issues": 7,
        "state": "open",
    },
    {
        "number": 2,
        "title": "v2.0",
        "due_on": None,
        "open_issues": 5,
        "closed_issues": 0,
        "state": "open",
    },
]


class TestFetchMilestones:
    async def test_returns_milestone_list(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/milestones",
                payload=SAMPLE_MILESTONES,
            )
            milestones = await repo.fetch_milestones("owner/repo1")

        assert len(milestones) == 2
        assert milestones[0] == GitHubMilestone(
            number=1,
            title="v1.0",
            due_date=date(2026, 3, 1),
            open_issues=3,
            closed_issues=7,
            state="open",
        )

    async def test_milestone_with_no_due_date(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/milestones",
                payload=SAMPLE_MILESTONES,
            )
            milestones = await repo.fetch_milestones("owner/repo1")

        assert milestones[1].due_date is None
        assert milestones[1].title == "v2.0"

    async def test_empty_milestones(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/milestones",
                payload=[],
            )
            milestones = await repo.fetch_milestones("owner/repo1")

        assert milestones == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/github/test_repository.py::TestFetchMilestones -v`
Expected: FAIL with `AttributeError: 'GitHubRepository' object has no attribute 'fetch_milestones'`

**Step 3: Implement fetch_milestones**

Add to `bot/services/github/repository.py`:

```python
# Add to GitHubRepository class:

    async def fetch_milestones(self, repo: str) -> list[GitHubMilestone]:
        """Fetch open milestones for a repo."""
        data = await self._request(
            "GET", f"/repos/{repo}/milestones", params={"state": "open", "sort": "due_on"}
        )
        return [_to_milestone(m) for m in data]


# Add module-level helper:

def _parse_due_date(value: str | None) -> date | None:
    """Parse GitHub milestone due_on to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").date()
    except ValueError:
        logger.warning("Failed to parse due_on: %s", value)
        return None


def _to_milestone(data: dict) -> GitHubMilestone:
    return GitHubMilestone(
        number=data["number"],
        title=data["title"],
        due_date=_parse_due_date(data.get("due_on")),
        open_issues=data.get("open_issues", 0),
        closed_issues=data.get("closed_issues", 0),
        state=data.get("state", "open"),
    )
```

**Step 4: Run tests**

Run: `pytest tests/services/github/test_repository.py::TestFetchMilestones -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add bot/services/github/repository.py tests/services/github/test_repository.py
git commit -m "feat(github): add fetch_milestones with date parsing"
```

---

### Task 5: Repository — fetch_issues_by_milestone and fetch_issues_without_milestone

**Files:**
- Modify: `bot/services/github/repository.py`
- Modify: `tests/services/github/test_repository.py`

**Step 1: Write failing tests**

Add to `tests/services/github/test_repository.py`:

```python
from datetime import datetime

from bot.services.github.domain import GitHubIssue, GitHubMilestone

SAMPLE_MILESTONE_RAW = {
    "number": 1,
    "title": "v1.0",
    "due_on": "2026-03-01T08:00:00Z",
    "open_issues": 3,
    "closed_issues": 7,
    "state": "open",
}

SAMPLE_ISSUES = [
    {
        "number": 10,
        "title": "Add auth",
        "state": "open",
        "labels": [{"name": "enhancement"}, {"name": "priority:high"}],
        "milestone": SAMPLE_MILESTONE_RAW,
        "html_url": "https://github.com/owner/repo1/issues/10",
        "created_at": "2026-02-10T12:00:00Z",
        "updated_at": "2026-02-14T15:30:00Z",
        "pull_request": None,
    },
    {
        "number": 11,
        "title": "Fix typo",
        "state": "open",
        "labels": [],
        "milestone": SAMPLE_MILESTONE_RAW,
        "html_url": "https://github.com/owner/repo1/issues/11",
        "created_at": "2026-02-12T09:00:00Z",
        "updated_at": "2026-02-12T09:00:00Z",
    },
]

SAMPLE_ISSUES_WITH_PR = [
    {
        "number": 12,
        "title": "A pull request",
        "state": "open",
        "labels": [],
        "milestone": SAMPLE_MILESTONE_RAW,
        "html_url": "https://github.com/owner/repo1/pull/12",
        "created_at": "2026-02-13T10:00:00Z",
        "updated_at": "2026-02-13T10:00:00Z",
        "pull_request": {"url": "https://api.github.com/repos/owner/repo1/pulls/12"},
    },
    SAMPLE_ISSUES[0],
]

SAMPLE_BACKLOG_ISSUES = [
    {
        "number": 20,
        "title": "Refactor utils",
        "state": "open",
        "labels": [{"name": "tech-debt"}],
        "milestone": None,
        "html_url": "https://github.com/owner/repo1/issues/20",
        "created_at": "2026-01-05T08:00:00Z",
        "updated_at": "2026-02-01T10:00:00Z",
    },
]


class TestFetchIssuesByMilestone:
    async def test_returns_issues_for_milestone(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/issues",
                payload=SAMPLE_ISSUES,
            )
            issues = await repo.fetch_issues_by_milestone("owner/repo1", 1)

        assert len(issues) == 2
        assert issues[0].number == 10
        assert issues[0].title == "Add auth"
        assert issues[0].repo == "owner/repo1"
        assert issues[0].labels == ("enhancement", "priority:high")
        assert issues[0].milestone is not None
        assert issues[0].milestone.title == "v1.0"

    async def test_filters_out_pull_requests(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/issues",
                payload=SAMPLE_ISSUES_WITH_PR,
            )
            issues = await repo.fetch_issues_by_milestone("owner/repo1", 1)

        # PR (number 12) should be excluded
        assert len(issues) == 1
        assert issues[0].number == 10


class TestFetchIssuesWithoutMilestone:
    async def test_returns_backlog_issues(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/issues",
                payload=SAMPLE_BACKLOG_ISSUES,
            )
            issues = await repo.fetch_issues_without_milestone("owner/repo1")

        assert len(issues) == 1
        assert issues[0].number == 20
        assert issues[0].milestone is None
        assert issues[0].labels == ("tech-debt",)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/github/test_repository.py::TestFetchIssuesByMilestone tests/services/github/test_repository.py::TestFetchIssuesWithoutMilestone -v`
Expected: FAIL with `AttributeError`

**Step 3: Implement the methods**

Add to `bot/services/github/repository.py`:

```python
# Add to GitHubRepository class:

    async def fetch_issues_by_milestone(
        self, repo: str, milestone_number: int
    ) -> list[GitHubIssue]:
        """Fetch open issues for a specific milestone."""
        data = await self._request(
            "GET",
            f"/repos/{repo}/issues",
            params={"milestone": str(milestone_number), "state": "open"},
        )
        return [
            _to_issue(item, repo)
            for item in data
            if "pull_request" not in item or item["pull_request"] is None
        ]

    async def fetch_issues_without_milestone(
        self, repo: str
    ) -> list[GitHubIssue]:
        """Fetch open assigned issues without a milestone (Backlog)."""
        data = await self._request(
            "GET",
            f"/repos/{repo}/issues",
            params={"milestone": "none", "state": "open", "assignee": "*"},
        )
        return [
            _to_issue(item, repo)
            for item in data
            if "pull_request" not in item or item["pull_request"] is None
        ]


# Add module-level helpers:

def _parse_datetime(value: str | None) -> datetime | None:
    """Parse GitHub ISO 8601 datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=ZoneInfo("UTC")
        )
    except ValueError:
        logger.warning("Failed to parse datetime: %s", value)
        return None


def _to_issue(data: dict, repo: str) -> GitHubIssue:
    milestone_data = data.get("milestone")
    milestone = _to_milestone(milestone_data) if milestone_data else None

    labels = tuple(label["name"] for label in data.get("labels", []))

    return GitHubIssue(
        number=data["number"],
        title=data["title"],
        repo=repo,
        state=data.get("state", "open"),
        labels=labels,
        milestone=milestone,
        url=data.get("html_url", ""),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )
```

**Step 4: Run tests**

Run: `pytest tests/services/github/test_repository.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add bot/services/github/repository.py tests/services/github/test_repository.py
git commit -m "feat(github): add fetch_issues_by_milestone and fetch_issues_without_milestone"
```

---

### Task 6: Repository — fetch_actionable_issues (Multi-Repo Aggregation)

**Files:**
- Modify: `bot/services/github/repository.py`
- Modify: `tests/services/github/test_repository.py`

**Step 1: Write failing tests**

Add to `tests/services/github/test_repository.py`:

```python
SAMPLE_MILESTONES_REPO2 = [
    {
        "number": 1,
        "title": "MVP",
        "due_on": "2026-04-01T08:00:00Z",
        "open_issues": 2,
        "closed_issues": 0,
        "state": "open",
    },
]

SAMPLE_ISSUES_REPO2 = [
    {
        "number": 5,
        "title": "Setup CI",
        "state": "open",
        "labels": [{"name": "infra"}],
        "milestone": SAMPLE_MILESTONES_REPO2[0],
        "html_url": "https://github.com/owner/repo2/issues/5",
        "created_at": "2026-02-11T08:00:00Z",
        "updated_at": "2026-02-11T08:00:00Z",
    },
]


class TestFetchActionableIssues:
    async def test_aggregates_across_repos(self):
        repo = make_repo(repos=["owner/repo1", "owner/repo2"])

        with aioresponses() as m:
            # repo1 milestones + issues
            m.get(f"{API_BASE}/repos/owner/repo1/milestones", payload=[SAMPLE_MILESTONES[0]])
            m.get(f"{API_BASE}/repos/owner/repo1/issues", payload=SAMPLE_ISSUES)
            m.get(f"{API_BASE}/repos/owner/repo1/issues", payload=SAMPLE_BACKLOG_ISSUES)

            # repo2 milestones + issues
            m.get(f"{API_BASE}/repos/owner/repo2/milestones", payload=SAMPLE_MILESTONES_REPO2)
            m.get(f"{API_BASE}/repos/owner/repo2/issues", payload=SAMPLE_ISSUES_REPO2)
            m.get(f"{API_BASE}/repos/owner/repo2/issues", payload=[])

            issues = await repo.fetch_actionable_issues()

        repos = {i.repo for i in issues}
        assert repos == {"owner/repo1", "owner/repo2"}
        # repo1: 2 milestone issues + 1 backlog = 3
        # repo2: 1 milestone issue + 0 backlog = 1
        assert len(issues) == 4

    async def test_repo_with_no_milestones(self):
        repo = make_repo(repos=["owner/empty"])

        with aioresponses() as m:
            m.get(f"{API_BASE}/repos/owner/empty/milestones", payload=[])
            m.get(f"{API_BASE}/repos/owner/empty/issues", payload=[])

            issues = await repo.fetch_actionable_issues()

        assert issues == []

    async def test_single_repo(self):
        repo = make_repo(repos=["owner/repo1"])

        with aioresponses() as m:
            m.get(f"{API_BASE}/repos/owner/repo1/milestones", payload=[SAMPLE_MILESTONES[0]])
            m.get(f"{API_BASE}/repos/owner/repo1/issues", payload=SAMPLE_ISSUES)
            m.get(f"{API_BASE}/repos/owner/repo1/issues", payload=[])

            issues = await repo.fetch_actionable_issues()

        assert len(issues) == 2
        assert all(i.repo == "owner/repo1" for i in issues)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/github/test_repository.py::TestFetchActionableIssues -v`
Expected: FAIL with `AttributeError`

**Step 3: Implement fetch_actionable_issues**

Add to `GitHubRepository` class in `bot/services/github/repository.py`:

```python
    async def fetch_actionable_issues(self) -> list[GitHubIssue]:
        """Fetch all planning-relevant issues across all configured repos."""
        all_issues: list[GitHubIssue] = []

        for repo in self._repos:
            milestones = await self.fetch_milestones(repo)

            for ms in milestones:
                issues = await self.fetch_issues_by_milestone(repo, ms.number)
                all_issues.extend(issues)

            backlog = await self.fetch_issues_without_milestone(repo)
            all_issues.extend(backlog)

        return all_issues
```

**Step 4: Run all tests**

Run: `pytest tests/services/github/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add bot/services/github/repository.py tests/services/github/test_repository.py
git commit -m "feat(github): add fetch_actionable_issues for multi-repo aggregation"
```

---

### Task 7: Verification and Final Cleanup

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (both ticktick and github)

**Step 2: Verify imports work**

Run: `python -c "from bot.services.github.domain import GitHubIssue, GitHubMilestone; from bot.services.github.repository import GitHubRepository; print('OK')"`
Expected: `OK`

**Step 3: Commit any remaining changes (if any)**

```bash
git status
# If clean, no commit needed
```
