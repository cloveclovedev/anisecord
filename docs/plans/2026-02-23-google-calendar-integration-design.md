# Google Calendar Integration for /daily-plan

## Overview

Add Google Calendar as a context source for the `/daily-plan` command. Currently the command only references TickTick tasks and GitHub Issues, which means it has no awareness of time constraints (work hours, personal commitments, etc.). By integrating Google Calendar data, the LLM can generate realistic, time-aware daily plans.

Related: Original daily-plan design (`2026-02-20-daily-plan-design.md`)

## Problem

The `/daily-plan` command generates plans based solely on task lists (TickTick, GitHub Issues). Without knowing the user's schedule, the LLM may produce infeasible plans — e.g., scheduling 8 hours of personal project work on a day fully occupied by the day job.

## Architecture

### New: ContextSource Protocol

Introduce a `ContextSource` protocol alongside the existing `TaskSource`. This separates "what to do" (tasks) from "when you can do it" (schedule constraints).

```python
@dataclass(frozen=True)
class ContextSourceResult:
    source_name: str       # e.g. "google_calendar"
    prompt_section: str    # Formatted text for LLM

class ContextSource(Protocol):
    @property
    def source_name(self) -> str: ...

    async def fetch_and_format(self) -> ContextSourceResult: ...
```

`ContextSourceResult` differs from `TaskSourceResult` in that it omits `item_count` — context is always relevant regardless of the number of events.

### New: Google Calendar Service

```
bot/services/google_calendar/
├── __init__.py
├── domain.py        # GoogleCalendarInfo, GoogleCalendarEvent
└── repository.py    # GoogleCalendarRepository (aiohttp + OAuth2)
```

Follows the same pattern as `bot/services/ticktick/` and `bot/services/github/`.

### New: Configuration File

```
daily_plan_config.toml   # Calendar interpretation rules (natural language)
```

Stores user-defined natural language rules for how the LLM should interpret calendar data. Designed for future migration to DB-backed per-user configuration.

### Modified Files

```
bot/features/daily_plan/
├── domain.py        # + ContextSource protocol
│                    # + ContextSourceResult dataclass
│                    # + GoogleCalendarContextSource adapter
│                    # + DailyPlanPromptBuilder changes
├── repository.py    # + Google Calendar credentials
│                    # + TOML config file loading
└── cog.py           # + ContextSource initialization & parallel fetch
```

### Updated Dependency Flow

```
cog.py
  ├── uses → domain.py (TaskSource, ContextSource, PromptBuilder)
  ├── uses → repository.py (DailyPlanConfigRepository)
  ├── uses → bot/services/ticktick/ (TickTickRepository)
  ├── uses → bot/services/github/ (GitHubRepository)
  ├── uses → bot/services/google_calendar/ (GoogleCalendarRepository)  ← NEW
  ├── uses → bot/services/discord/ (DiscordRepository)
  └── uses → bot/services/llm/ (LLMRepository)
```

## Domain Model

### Google Calendar Service

```python
@dataclass(frozen=True)
class GoogleCalendarInfo:
    id: str
    summary: str  # Calendar name (e.g. "cloveclove", "Work")

@dataclass(frozen=True)
class GoogleCalendarEvent:
    id: str
    summary: str                  # Event title
    calendar: GoogleCalendarInfo  # Owning calendar
    start: datetime
    end: datetime
    is_all_day: bool
    location: str | None
    status: str                   # "confirmed", "tentative", "cancelled"
```

### GoogleCalendarContextSource Adapter

```python
class GoogleCalendarContextSource:
    def __init__(
        self,
        repository: GoogleCalendarRepository,
        calendar_context: str,  # Natural language rules from TOML
        timezone: str,
    ): ...

    async def fetch_and_format(self) -> ContextSourceResult:
        # 1. Fetch today's events (detailed)
        # 2. Fetch rest-of-week events (overview)
        # 3. Format with calendar names in chronological order
        # 4. Append calendar_context (interpretation rules)
```

### Output Format (prompt section)

```
## 今日のスケジュール (2026-02-23 月曜日)
- 07:30-08:00 [mkuri] HOM | Shower
- 08:30-09:00 [mkuri] CNM | Walk
- 10:00-20:00 [Work] WRK | @品川
- 16:30-17:00 [mkuri] DEV | Reset claude
- 20:00-20:30 [mkuri] GO | Home

## 今週の残りのスケジュール概要
### 2/24 (火)
- 10:30-20:00 [Work] WRK | @品川
- 13:30-23:00 [cloveclove] CLV | @Tsutaya
### 2/25 (水)
- 10:30-20:00 [Work] WRK | @品川
...

## カレンダーの解釈ルール
clovecloveカレンダーは個人事業の作業時間。
Workカレンダーは本業の時間。
...
```

## Google Calendar API

### Authentication

OAuth2 with refresh token, same pattern as TickTick. Read-only scope: `https://www.googleapis.com/auth/calendar.events.readonly`.

### HTTP Client

aiohttp direct calls (consistent with TickTick/GitHub services). No google-api-python-client dependency.

### Endpoints

- `GET https://www.googleapis.com/calendar/v3/users/me/calendarList` — list all calendars
- `GET https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events` — list events with `timeMin`/`timeMax` parameters

### Repository

```python
class GoogleCalendarRepository:
    def __init__(self, client_id, client_secret, access_token, refresh_token): ...

    async def fetch_calendars(self) -> list[GoogleCalendarInfo]: ...
    async def fetch_events(
        self,
        time_min: datetime,  # Start of today
        time_max: datetime,  # End of week
    ) -> list[GoogleCalendarEvent]: ...
    # Fetches from all calendars, auto-refreshes OAuth2 token on 401
```

## Prompt Integration

### Updated Prompt Structure

```
[System prompt]
[Context: Google Calendar]      ← NEW (constraints BEFORE tasks)
[Tasks: TickTick]
[Tasks: GitHub Issues]
[Previous messages (2nd+ runs)]
```

Context is placed before tasks so the LLM recognizes time constraints before reviewing the task list.

### Updated build_prompt() Signature

```python
@staticmethod
def build_prompt(
    task_results: list[TaskSourceResult],
    context_results: list[ContextSourceResult],  # ← NEW
    previous_messages: list[str],
    date: date,
    language: str = "ja",
) -> str:
```

### System Prompt Addition

Add instruction for the LLM to consider schedule constraints when prioritizing tasks and estimating what can realistically be accomplished in the available time.

## Configuration

### Environment Variables (additions)

```
# Google Calendar (required if google_calendar source enabled)
GOOGLE_CALENDAR_CLIENT_ID=...
GOOGLE_CALENDAR_CLIENT_SECRET=...
GOOGLE_CALENDAR_ACCESS_TOKEN=...
GOOGLE_CALENDAR_REFRESH_TOKEN=...

# Updated default
DAILY_PLAN_SOURCES=ticktick,github,google_calendar
```

### TOML Configuration File

```toml
# daily_plan_config.toml

[calendar]
context = """
clovecloveカレンダーは個人事業の作業時間。
Workカレンダーは本業の時間。
mkuriカレンダーは個人の予定。
Sleepは睡眠時間。
これらの情報から、今日使える作業時間を
判断してタスクの優先順位を決めてください。
"""
```

Read using `tomllib` (Python 3.11+ standard library, no dependency added).

Future: migrate to DB-backed per-user configuration via Discord commands.

## Data Flow (Updated)

1. User runs `/daily-plan` or scheduler triggers
2. Load `DailyPlanConfig` (env vars + TOML)
3. Initialize `TaskSource`s and `ContextSource`s
4. Concurrent fetch from all sources:
   - TickTickTaskSource → TickTick API
   - GitHubTaskSource → GitHub API
   - GoogleCalendarContextSource → Google Calendar API
5. `DailyPlanPromptBuilder.build_prompt()` assembles prompt (context before tasks)
6. LLM generates time-aware plan
7. Post to Discord thread

## Error Handling

Same strategy as existing sources:
- Google Calendar failure: skip, continue with other sources, note failure in status
- Missing credentials: `has_source("google_calendar")` returns false, source not initialized
- TOML file missing/malformed: fallback to empty context string (events still shown, just without interpretation rules)

## Testing

```
tests/services/google_calendar/
├── test_domain.py         # GoogleCalendarInfo, GoogleCalendarEvent
└── test_repository.py     # API calls (aioresponses), OAuth2 refresh, pagination

tests/features/daily_plan/
├── test_domain.py         # + ContextSourceResult
                           # + GoogleCalendarContextSource formatting
                           # + PromptBuilder context integration
                           # + Backward compatibility (empty context)
└── test_repository.py     # + Google Calendar credential parsing
                           # + has_source("google_calendar")
                           # + TOML config loading
```
