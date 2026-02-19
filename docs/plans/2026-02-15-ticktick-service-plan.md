# TickTick Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a TickTick API integration service that fetches today's and overdue tasks as domain objects.

**Architecture:** Service layer at `bot/services/ticktick/` following existing Repository pattern (domain.py + repository.py). OAuth 2.0 auth in a dedicated auth.py. aiohttp for HTTP calls. TDD with pytest + aioresponses.

**Tech Stack:** Python 3.13, aiohttp, pytest, aioresponses, asyncio

---

### Task 1: Add dependencies and pytest configuration

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add runtime and dev dependencies**

Run:
```bash
uv add aiohttp
uv add --dev pytest pytest-asyncio aioresponses
```

**Step 2: Add pytest configuration to pyproject.toml**

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 3: Verify pytest runs**

Run: `uv run pytest --co -q`
Expected: `no tests ran` (no errors)

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add aiohttp, pytest, and aioresponses dependencies"
```

---

### Task 2: Create domain model with tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/services/__init__.py`
- Create: `tests/services/ticktick/__init__.py`
- Create: `tests/services/ticktick/test_domain.py`
- Create: `bot/services/ticktick/__init__.py`
- Create: `bot/services/ticktick/domain.py`

**Step 1: Write the failing tests**

Create `tests/services/ticktick/test_domain.py`:
```python
from bot.services.ticktick.domain import (
    TaskPriority,
    TaskStatus,
    SubTaskStatus,
    TickTickSubTask,
    TickTickTask,
    TickTickProject,
)


class TestTaskPriority:
    def test_values_match_ticktick_api(self):
        assert TaskPriority.NONE == 0
        assert TaskPriority.LOW == 1
        assert TaskPriority.MEDIUM == 3
        assert TaskPriority.HIGH == 5


class TestTaskStatus:
    def test_values_match_ticktick_api(self):
        assert TaskStatus.ACTIVE == 0
        assert TaskStatus.COMPLETED == 2


class TestSubTaskStatus:
    def test_values_differ_from_task_status(self):
        assert SubTaskStatus.ACTIVE == 0
        assert SubTaskStatus.COMPLETED == 1


class TestTickTickSubTask:
    def test_creation(self):
        sub = TickTickSubTask(title="Buy milk", status=SubTaskStatus.ACTIVE, sort_order=0)
        assert sub.title == "Buy milk"
        assert sub.status == SubTaskStatus.ACTIVE
        assert sub.sort_order == 0

    def test_frozen(self):
        sub = TickTickSubTask(title="Buy milk", status=SubTaskStatus.ACTIVE, sort_order=0)
        try:
            sub.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestTickTickTask:
    def test_creation_minimal(self):
        task = TickTickTask(
            id="task1",
            title="Test task",
            project_id="proj1",
            project_name="Work",
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.HIGH,
            is_overdue=False,
        )
        assert task.id == "task1"
        assert task.title == "Test task"
        assert task.project_name == "Work"
        assert task.priority == TaskPriority.HIGH
        assert task.is_overdue is False
        assert task.content == ""
        assert task.tags == ()
        assert task.due_date is None
        assert task.sub_tasks == ()

    def test_creation_with_all_fields(self):
        from datetime import datetime

        sub = TickTickSubTask(title="Step 1", status=SubTaskStatus.COMPLETED, sort_order=0)
        task = TickTickTask(
            id="task2",
            title="Full task",
            project_id="proj2",
            project_name="Personal",
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.MEDIUM,
            is_overdue=True,
            content="Some notes",
            tags=("urgent", "home"),
            due_date=datetime(2026, 2, 14, 9, 0),
            start_date=datetime(2026, 2, 14, 8, 0),
            is_all_day=True,
            sub_tasks=(sub,),
            created_time=datetime(2026, 2, 10),
            modified_time=datetime(2026, 2, 14),
        )
        assert task.is_overdue is True
        assert task.tags == ("urgent", "home")
        assert len(task.sub_tasks) == 1
        assert task.sub_tasks[0].title == "Step 1"

    def test_frozen(self):
        task = TickTickTask(
            id="t", title="t", project_id="p", project_name="P",
            status=TaskStatus.ACTIVE, priority=TaskPriority.NONE, is_overdue=False,
        )
        try:
            task.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestTickTickProject:
    def test_creation(self):
        proj = TickTickProject(id="p1", name="Work")
        assert proj.id == "p1"
        assert proj.name == "Work"
        assert proj.color is None

    def test_with_color(self):
        proj = TickTickProject(id="p2", name="Personal", color="#FF0000")
        assert proj.color == "#FF0000"
```

Also create empty `__init__.py` files:
- `tests/__init__.py`
- `tests/services/__init__.py`
- `tests/services/ticktick/__init__.py`
- `bot/services/ticktick/__init__.py`

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/services/ticktick/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.services.ticktick'`

**Step 3: Write the domain model**

Create `bot/services/ticktick/domain.py`:
```python
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional


class TaskPriority(IntEnum):
    """TickTick API priority values."""
    NONE = 0
    LOW = 1
    MEDIUM = 3
    HIGH = 5


class TaskStatus(IntEnum):
    """TickTick API task status values."""
    ACTIVE = 0
    COMPLETED = 2


class SubTaskStatus(IntEnum):
    """TickTick API subtask (checklist item) status values."""
    ACTIVE = 0
    COMPLETED = 1


@dataclass(frozen=True)
class TickTickSubTask:
    title: str
    status: SubTaskStatus
    sort_order: int


@dataclass(frozen=True)
class TickTickTask:
    id: str
    title: str
    project_id: str
    project_name: str
    status: TaskStatus
    priority: TaskPriority
    is_overdue: bool
    content: str = ""
    tags: tuple[str, ...] = ()
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    is_all_day: bool = False
    sub_tasks: tuple[TickTickSubTask, ...] = ()
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None


@dataclass(frozen=True)
class TickTickProject:
    id: str
    name: str
    color: Optional[str] = None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/services/ticktick/test_domain.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add bot/services/ticktick/ tests/
git commit -m "feat(ticktick): add domain models for TickTick service"
```

---

### Task 3: Implement OAuth authentication with tests

**Files:**
- Create: `tests/services/ticktick/test_auth.py`
- Create: `bot/services/ticktick/auth.py`

**Step 1: Write the failing tests**

Create `tests/services/ticktick/test_auth.py`:
```python
import asyncio
import time

import aiohttp
import pytest
from aioresponses import aioresponses

from bot.services.ticktick.auth import TickTickAuth, TickTickAuthError

TICKTICK_TOKEN_URL = "https://ticktick.com/oauth/token"


class TestGetValidToken:
    async def test_returns_current_token_when_not_expired(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="valid_token",
            refresh_token="rtoken",
            expires_at=time.time() + 3600,
        )
        token = await auth.get_valid_token()
        assert token == "valid_token"

    async def test_returns_current_token_when_expires_at_is_zero(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="token_no_expiry",
            refresh_token="rtoken",
            expires_at=0.0,
        )
        token = await auth.get_valid_token()
        assert token == "token_no_expiry"

    async def test_refreshes_when_near_expiry(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old_token",
            refresh_token="rtoken",
            expires_at=time.time() + 30,  # Within 60s buffer
        )
        with aioresponses() as m:
            m.post(
                TICKTICK_TOKEN_URL,
                payload={
                    "access_token": "new_token",
                    "refresh_token": "new_rtoken",
                    "expires_in": 3600,
                },
            )
            token = await auth.get_valid_token()
        assert token == "new_token"
        assert auth.refresh_token == "new_rtoken"


class TestRefresh:
    async def test_successful_refresh(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="old_refresh",
        )
        with aioresponses() as m:
            m.post(
                TICKTICK_TOKEN_URL,
                payload={
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",
                    "expires_in": 7200,
                },
            )
            await auth.refresh()

        assert auth.access_token == "new_access"
        assert auth.refresh_token == "new_refresh"
        assert auth.expires_at > time.time()

    async def test_refresh_without_new_refresh_token(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="keep_this",
        )
        with aioresponses() as m:
            m.post(
                TICKTICK_TOKEN_URL,
                payload={"access_token": "new_access", "expires_in": 3600},
            )
            await auth.refresh()

        assert auth.access_token == "new_access"
        assert auth.refresh_token == "keep_this"

    async def test_refresh_failure_raises_auth_error(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="bad_refresh",
        )
        with aioresponses() as m:
            m.post(TICKTICK_TOKEN_URL, status=400, payload={"error": "invalid_grant"})
            with pytest.raises(TickTickAuthError, match="400"):
                await auth.refresh()

    async def test_concurrent_refresh_only_calls_api_once(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="rtoken",
            expires_at=0.0,
        )
        call_count = 0

        with aioresponses() as m:

            def callback(url, **kwargs):
                nonlocal call_count
                call_count += 1
                return aioresponses.CallbackResult(
                    payload={
                        "access_token": "refreshed",
                        "refresh_token": "new_r",
                        "expires_in": 3600,
                    }
                )

            m.post(TICKTICK_TOKEN_URL, callback=callback, repeat=True)

            await asyncio.gather(auth.refresh(), auth.refresh(), auth.refresh())

        # Due to double-check pattern, only 1 actual API call should be made
        assert call_count == 1
        assert auth.access_token == "refreshed"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/services/ticktick/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.services.ticktick.auth'`

**Step 3: Write the auth module**

Create `bot/services/ticktick/auth.py`:
```python
import asyncio
import logging
import time
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

TICKTICK_TOKEN_URL = "https://ticktick.com/oauth/token"


class TickTickAuthError(Exception):
    """Raised when OAuth token operations fail."""


@dataclass
class TickTickAuth:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: float = 0.0
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def get_valid_token(self) -> str:
        """Return a valid access token. Proactively refreshes 60s before expiry."""
        if self.expires_at and time.time() >= self.expires_at - 60:
            await self.refresh()
        return self.access_token

    async def refresh(self) -> None:
        """Refresh the access token. Safe to call from multiple coroutines."""
        async with self._refresh_lock:
            # Double-check: another coroutine may have already refreshed
            if self.expires_at and time.time() < self.expires_at - 60:
                return

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    TICKTICK_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "Token refresh failed: status=%d body=%s",
                            resp.status,
                            body,
                        )
                        raise TickTickAuthError(
                            f"Token refresh failed ({resp.status}): {body}"
                        )

                    data = await resp.json()
                    self.access_token = data["access_token"]
                    if "refresh_token" in data:
                        self.refresh_token = data["refresh_token"]
                    if "expires_in" in data:
                        self.expires_at = time.time() + data["expires_in"]

                    logger.info("TickTick token refreshed successfully")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/services/ticktick/test_auth.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add bot/services/ticktick/auth.py tests/services/ticktick/test_auth.py
git commit -m "feat(ticktick): add OAuth 2.0 authentication with token refresh"
```

---

### Task 4: Implement repository with tests

**Files:**
- Create: `tests/services/ticktick/test_repository.py`
- Create: `bot/services/ticktick/repository.py`

**Step 1: Write the failing tests**

Create `tests/services/ticktick/test_repository.py`:

```python
import time
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from aioresponses import aioresponses

from bot.services.ticktick.auth import TickTickAuth
from bot.services.ticktick.domain import (
    SubTaskStatus,
    TaskPriority,
    TaskStatus,
    TickTickProject,
    TickTickTask,
)
from bot.services.ticktick.repository import TickTickRepository

API_BASE = "https://api.ticktick.com/open/v1"
JST = ZoneInfo("Asia/Tokyo")


def make_auth() -> TickTickAuth:
    return TickTickAuth(
        client_id="cid",
        client_secret="csecret",
        access_token="test_token",
        refresh_token="rtoken",
        expires_at=time.time() + 3600,
    )


# --- Sample API response fixtures ---

SAMPLE_PROJECTS = [
    {"id": "proj1", "name": "Work", "color": "#4772FA"},
    {"id": "proj2", "name": "Personal", "color": None},
]

SAMPLE_PROJECT_DATA_PROJ1 = {
    "tasks": [
        {
            "id": "task1",
            "title": "Review PR",
            "projectId": "proj1",
            "status": 0,
            "priority": 5,
            "content": "Check the new feature branch",
            "tags": ["dev"],
            "dueDate": "2026-02-15T09:00:00.000+0000",
            "startDate": "2026-02-15T08:00:00.000+0000",
            "isAllDay": False,
            "items": [
                {"title": "Read code", "status": 0, "sortOrder": 0},
                {"title": "Leave comments", "status": 1, "sortOrder": 1},
            ],
            "createdTime": "2026-02-10T00:00:00.000+0000",
            "modifiedTime": "2026-02-14T12:00:00.000+0000",
        },
        {
            "id": "task2",
            "title": "Completed task",
            "projectId": "proj1",
            "status": 2,
            "priority": 0,
            "dueDate": "2026-02-15T09:00:00.000+0000",
        },
    ]
}

SAMPLE_PROJECT_DATA_PROJ2 = {
    "tasks": [
        {
            "id": "task3",
            "title": "Overdue grocery shopping",
            "projectId": "proj2",
            "status": 0,
            "priority": 1,
            "dueDate": "2026-02-13T00:00:00.000+0000",
            "isAllDay": True,
        },
        {
            "id": "task4",
            "title": "Future task",
            "projectId": "proj2",
            "status": 0,
            "priority": 3,
            "dueDate": "2026-02-20T00:00:00.000+0000",
        },
        {
            "id": "task5",
            "title": "No due date task",
            "projectId": "proj2",
            "status": 0,
            "priority": 0,
        },
    ]
}


class TestFetchProjects:
    async def test_returns_project_list(self):
        repo = TickTickRepository(make_auth())
        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            projects = await repo.fetch_projects()

        assert len(projects) == 2
        assert projects[0] == TickTickProject(id="proj1", name="Work", color="#4772FA")
        assert projects[1] == TickTickProject(id="proj2", name="Personal", color=None)


class TestFetchActionableTasks:
    @patch("bot.services.ticktick.repository._today_jst")
    async def test_returns_today_and_overdue_tasks(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            m.get(f"{API_BASE}/project/proj1/data", payload=SAMPLE_PROJECT_DATA_PROJ1)
            m.get(f"{API_BASE}/project/proj2/data", payload=SAMPLE_PROJECT_DATA_PROJ2)

            tasks = await repo.fetch_actionable_tasks()

        # task1: due today, active → included
        # task2: due today, completed → excluded
        # task3: overdue (Feb 13), active → included
        # task4: future (Feb 20) → excluded
        # task5: no due date → excluded
        assert len(tasks) == 2
        titles = {t.title for t in tasks}
        assert titles == {"Review PR", "Overdue grocery shopping"}

    @patch("bot.services.ticktick.repository._today_jst")
    async def test_overdue_flag_is_set_correctly(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            m.get(f"{API_BASE}/project/proj1/data", payload=SAMPLE_PROJECT_DATA_PROJ1)
            m.get(f"{API_BASE}/project/proj2/data", payload=SAMPLE_PROJECT_DATA_PROJ2)

            tasks = await repo.fetch_actionable_tasks()

        task_map = {t.title: t for t in tasks}
        assert task_map["Review PR"].is_overdue is False
        assert task_map["Overdue grocery shopping"].is_overdue is True

    @patch("bot.services.ticktick.repository._today_jst")
    async def test_task_fields_are_converted_correctly(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            m.get(f"{API_BASE}/project/proj1/data", payload=SAMPLE_PROJECT_DATA_PROJ1)
            m.get(f"{API_BASE}/project/proj2/data", payload=SAMPLE_PROJECT_DATA_PROJ2)

            tasks = await repo.fetch_actionable_tasks()

        task = next(t for t in tasks if t.title == "Review PR")
        assert task.id == "task1"
        assert task.project_id == "proj1"
        assert task.project_name == "Work"
        assert task.status == TaskStatus.ACTIVE
        assert task.priority == TaskPriority.HIGH
        assert task.content == "Check the new feature branch"
        assert task.tags == ("dev",)
        assert task.is_all_day is False
        assert len(task.sub_tasks) == 2
        assert task.sub_tasks[0].title == "Read code"
        assert task.sub_tasks[0].status == SubTaskStatus.ACTIVE
        assert task.sub_tasks[1].status == SubTaskStatus.COMPLETED

    @patch("bot.services.ticktick.repository._today_jst")
    async def test_empty_projects(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=[])
            tasks = await repo.fetch_actionable_tasks()

        assert tasks == []


class TestRequestRetry:
    async def test_retries_on_401(self):
        auth = make_auth()
        repo = TickTickRepository(auth)

        with aioresponses() as m:
            # First call returns 401
            m.get(f"{API_BASE}/project", status=401)
            # After refresh, second call succeeds
            m.post(
                "https://ticktick.com/oauth/token",
                payload={
                    "access_token": "new_token",
                    "expires_in": 3600,
                },
            )
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)

            projects = await repo.fetch_projects()

        assert len(projects) == 2
        assert auth.access_token == "new_token"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/services/ticktick/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.services.ticktick.repository'`

**Step 3: Write the repository**

Create `bot/services/ticktick/repository.py`:

```python
import logging
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .auth import TickTickAuth
from .domain import (
    SubTaskStatus,
    TaskPriority,
    TaskStatus,
    TickTickProject,
    TickTickSubTask,
    TickTickTask,
)

logger = logging.getLogger(__name__)

TICKTICK_API_BASE = "https://api.ticktick.com/open/v1"
JST = ZoneInfo("Asia/Tokyo")


def _today_jst() -> date:
    """Return today's date in JST. Extracted for testability."""
    return datetime.now(JST).date()


class TickTickRepository:
    def __init__(self, auth: TickTickAuth):
        self._auth = auth

    async def fetch_projects(self) -> list[TickTickProject]:
        """Fetch all projects."""
        data = await self._request("GET", "/project")
        return [_to_project(p) for p in data]

    async def fetch_actionable_tasks(self) -> list[TickTickTask]:
        """Fetch active tasks that are due today or overdue, across all projects."""
        projects = await self.fetch_projects()
        project_map = {p.id: p.name for p in projects}

        today = _today_jst()
        result: list[TickTickTask] = []

        for project in projects:
            data = await self._request("GET", f"/project/{project.id}/data")
            for raw_task in data.get("tasks", []):
                task = _to_task(raw_task, project_map, today)
                if task is None:
                    continue
                result.append(task)

        return result

    async def _request(self, method: str, path: str) -> Any:
        """Make an API request. Retries once on 401 after refreshing the token."""
        token = await self._auth.get_valid_token()
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{TICKTICK_API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status == 401:
                    await self._auth.refresh()
                    token = await self._auth.get_valid_token()
                    # Retry once with new token — need a new request
                    async with session.request(
                        method,
                        f"{TICKTICK_API_BASE}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()

                resp.raise_for_status()
                return await resp.json()


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse TickTick datetime string to datetime object."""
    if not value:
        return None
    # TickTick format: "2026-02-15T09:00:00.000+0000"
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        logger.warning("Failed to parse datetime: %s", value)
        return None


def _to_project(data: dict) -> TickTickProject:
    return TickTickProject(
        id=data["id"],
        name=data["name"],
        color=data.get("color"),
    )


def _to_task(
    data: dict, project_map: dict[str, str], today: date
) -> TickTickTask | None:
    """Convert API response to domain object. Returns None if not actionable."""
    status = TaskStatus(data.get("status", 0))
    if status != TaskStatus.ACTIVE:
        return None

    due_date = _parse_datetime(data.get("dueDate"))
    if due_date is None:
        return None

    due_date_local = due_date.astimezone(JST).date()
    if due_date_local > today:
        return None

    is_overdue = due_date_local < today

    sub_tasks = tuple(
        TickTickSubTask(
            title=item.get("title", ""),
            status=SubTaskStatus(item.get("status", 0)),
            sort_order=item.get("sortOrder", 0),
        )
        for item in data.get("items", [])
    )

    tags = tuple(data.get("tags", []))

    return TickTickTask(
        id=data["id"],
        title=data["title"],
        project_id=data.get("projectId", ""),
        project_name=project_map.get(data.get("projectId", ""), ""),
        status=status,
        priority=TaskPriority(data.get("priority", 0)),
        is_overdue=is_overdue,
        content=data.get("content", ""),
        tags=tags,
        due_date=due_date,
        start_date=_parse_datetime(data.get("startDate")),
        is_all_day=data.get("isAllDay", False),
        sub_tasks=sub_tasks,
        created_time=_parse_datetime(data.get("createdTime")),
        modified_time=_parse_datetime(data.get("modifiedTime")),
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/services/ticktick/test_repository.py -v`
Expected: All tests PASS

**Step 5: Run all ticktick tests together**

Run: `uv run pytest tests/services/ticktick/ -v`
Expected: All tests PASS (domain + auth + repository)

**Step 6: Commit**

```bash
git add bot/services/ticktick/repository.py tests/services/ticktick/test_repository.py
git commit -m "feat(ticktick): add repository for fetching actionable tasks"
```

---

### Task 5: Final verification and cleanup

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Verify module imports work**

Run:
```bash
uv run python -c "from bot.services.ticktick.domain import TickTickTask, TaskPriority; print('domain OK')"
uv run python -c "from bot.services.ticktick.auth import TickTickAuth, TickTickAuthError; print('auth OK')"
uv run python -c "from bot.services.ticktick.repository import TickTickRepository; print('repository OK')"
```
Expected: All print `OK`

**Step 3: Commit any cleanup if needed**

If no changes needed, skip this step.
