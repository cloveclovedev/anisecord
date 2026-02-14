# TickTick Service Design

**Date:** 2026-02-15
**Issue:** #37 (Epic: #35)
**Status:** Approved

## Overview

A service layer that integrates with the TickTick API to provide task data as domain objects. Serves as a data source for the Planning feature (daily plan / weekly plan).

## Scope

- Create data access layer at `bot/services/ticktick/`
- Fetch today's tasks + overdue (past due, incomplete) tasks
- OAuth 2.0 authentication (Phase 1: manual token acquisition, stored in .env)
- Return domain objects for consumption by the planning feature

## Out of Scope

- `/daily-plan` command (separate ticket)
- Auto-posting to diary channel (separate ticket)
- Multi-user support (Phase 2)
- Write operations to TickTick

## Directory Structure

```
bot/services/ticktick/
├── __init__.py
├── domain.py          # Domain models (TickTickTask, TickTickProject, etc.)
├── repository.py      # API calls + domain conversion
├── auth.py            # OAuth 2.0 token management
```

## Domain Model

```python
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
    project_name: str         # Resolved project name (no reverse lookup needed)
    status: TaskStatus
    priority: TaskPriority
    is_overdue: bool          # Whether due date is before today
    content: str = ""         # Task notes/description
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

### Design Decisions

- `frozen=True` for consistency with existing patterns (DiscordPost, User)
- `project_name` included in Task so consumers don't need to resolve project_id
- `tuple` for immutability (matches existing `allowed_features: tuple` pattern)
- `TaskPriority` / `TaskStatus` use TickTick API's actual integer values (0/1/3/5 for priority, 0/2 for task status)
- `SubTaskStatus` separated from `TaskStatus` because subtasks (checklist items) use different values (0/1 instead of 0/2)
- Subtasks represent TickTick's checklist items (simpler structure than full tasks)

## OAuth Authentication (`auth.py`)

### Flow

Phase 1: Manually obtain tokens from TickTick developer portal → store in .env

### Implementation

```python
class TickTickAuthError(Exception):
    """Raised when OAuth token operations fail."""

@dataclass
class TickTickAuth:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: float = 0.0
    _refresh_lock: asyncio.Lock  # Concurrency control

    async def get_valid_token(self) -> str:
        """Return valid access token. Proactively refreshes 60s before expiry."""
        if self.expires_at and time.time() >= self.expires_at - 60:
            await self.refresh()
        return self.access_token

    async def refresh(self) -> None:
        """Refresh access token. Thread-safe via asyncio.Lock + double-check."""
        async with self._refresh_lock:
            # Double-check: skip if another coroutine already refreshed
            if self.expires_at and time.time() < self.expires_at - 60:
                return
            # POST https://ticktick.com/oauth/token
            # grant_type=refresh_token
            # On failure: log response body, raise TickTickAuthError
            # On success: update access_token, refresh_token, expires_at
```

### Security Considerations

| Priority | Issue | Mitigation |
|----------|-------|------------|
| High | Concurrent refresh race condition | `asyncio.Lock` + double-check pattern |
| High | Token staleness after restart | Persist rotated tokens (TODO: Phase 1 follow-up) |
| High | Poor diagnostics on refresh failure | Log response body + custom `TickTickAuthError` |
| Medium | No request timeout | `aiohttp.ClientTimeout(total=10)` |
| Medium | No proactive refresh | Track `expires_at`, refresh 60s before expiry |

## Repository (`repository.py`)

### API Endpoints Used

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/project` | List all projects |
| GET | `/project/{id}/data` | Get project data including tasks |

Base URL: `https://api.ticktick.com/open/v1`
Auth header: `Authorization: Bearer {access_token}`

### Key Methods

```python
class TickTickRepository:
    def __init__(self, auth: TickTickAuth):
        self._auth = auth

    async def fetch_projects(self) -> list[TickTickProject]:
        """Fetch all projects."""

    async def fetch_actionable_tasks(self) -> list[TickTickTask]:
        """Fetch active tasks that are due today or overdue, across all projects."""
        # 1. Fetch all projects
        # 2. For each project: GET /project/{id}/data
        # 3. Filter: due_date <= today AND status == ACTIVE
        # 4. Convert to domain objects with is_overdue flag
```

### Design Decisions

- No "today's tasks" endpoint in TickTick API → fetch all projects then filter
- `_request()` centralizes OAuth 401 retry (refresh + retry once)
- `_to_task()` isolates API response → domain object conversion
- Timezone: Asia/Tokyo (from User settings; hardcoded in Phase 1)

## HTTP Client

- **aiohttp** (not httpx) for new service implementation
- Migration of existing `bot/services/llm/utils.py` (httpx) is a separate ticket

## Environment Variables

```
TICKTICK_CLIENT_ID=<OAuth app client ID>
TICKTICK_CLIENT_SECRET=<OAuth app client secret>
TICKTICK_ACCESS_TOKEN=<manually obtained access token>
TICKTICK_REFRESH_TOKEN=<manually obtained refresh token>
```

## Testing

```
tests/services/ticktick/
├── test_domain.py        # Domain model tests
├── test_repository.py    # API response mock → domain conversion tests
├── test_auth.py          # Token refresh tests (including concurrency safety)
```

### Mock Strategy

- `aioresponses` or `unittest.mock.AsyncMock` for mocking aiohttp responses
- Test targets: domain conversion logic, today/overdue date filtering, token refresh flow

## Dependencies

- `aiohttp` — HTTP client (new addition)
- `aioresponses` — Test mock for aiohttp (dev dependency, new addition)

## Future Considerations (Out of Scope)

- Token persistence: write-back to .env or JSON file (Phase 1 follow-up)
- Multi-user: DB storage + encryption (Phase 2)
- Weekly tasks fetching
- Write API support (task completion marking, etc.)
