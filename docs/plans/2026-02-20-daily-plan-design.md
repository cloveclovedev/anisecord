# /daily-plan Feature Design

## Overview

Implement the `/daily-plan` command that aggregates tasks from external tools (TickTick, GitHub Issues), generates a structured daily plan via LLM, and posts it to a designated Discord thread. Supports both manual trigger and scheduled auto-posting.

Related: Epic #35, Task #39

## Architecture

### File Structure

```
bot/services/discord/
├── domain.py           # DiscordPost (existing)
└── repository.py       # DiscordRepository (existing)
                        #   + find_or_create_thread(channel, thread_name)
                        #   + send_to_thread(thread, content)
                        #   + fetch_thread_messages(thread)

bot/features/daily_plan/
├── cog.py              # /daily-plan command + tasks.loop scheduler
├── domain.py           # TaskSource protocol, TaskSourceResult
│                       #   + TickTickTaskSource adapter
│                       #   + GitHubTaskSource adapter
│                       #   + DailyPlanPromptBuilder
└── repository.py       # DailyPlanConfigRepository (env var settings)
```

### Dependency Flow

```
cog.py
  ├── uses → domain.py (TaskSource, PromptBuilder)
  ├── uses → repository.py (DailyPlanConfigRepository)
  ├── uses → bot/services/ticktick/ (TickTickRepository)
  ├── uses → bot/services/github/ (GitHubRepository)
  ├── uses → bot/services/discord/ (DiscordRepository)
  └── uses → bot/services/llm/ (LLMRepository)
```

## Domain Model

### TaskSource Protocol

Each data source implements the `TaskSource` protocol. Instead of converting to a unified intermediate type, each source formats its own data richly for the LLM prompt, preserving all source-specific context (sub-task progress, milestone progress, labels, etc.).

```python
class TaskSource(Protocol):
    @property
    def source_name(self) -> str: ...

    async def fetch_and_format(self) -> TaskSourceResult: ...

@dataclass(frozen=True)
class TaskSourceResult:
    source_name: str
    prompt_section: str   # Rich text for LLM prompt
    item_count: int       # For handling zero-task scenarios
```

### Adapters

- **TickTickTaskSource**: Wraps `TickTickRepository.fetch_actionable_tasks()`. Formats with priority levels, sub-task progress, project names, due dates, overdue status.
- **GitHubTaskSource**: Wraps `GitHubRepository.fetch_actionable_issues()`. Formats with milestone progress, labels, repository names, issue URLs.

### Prompt Builder

`DailyPlanPromptBuilder.build_prompt()` assembles the final LLM prompt by:
1. Combining all source sections
2. Including existing thread messages (for 2nd+ runs of the day)
3. Adding formatting instructions and language preference

## Data Flow

### Manual Execution (`/daily-plan`)

1. User runs `/daily-plan`
2. `interaction.response.defer()` (processing takes time)
3. `DailyPlanConfigRepository` loads settings (channel ID, thread format, etc.)
4. Each `TaskSource.fetch_and_format()` runs concurrently
   - TickTickTaskSource → TickTick API → rich text section
   - GitHubTaskSource → GitHub API → rich text section
5. `DiscordRepository.find_or_create_thread()` on journal channel
   - Searches for today's thread (e.g., "2026-02-20 日報")
   - Existing: returns thread + fetches existing messages
   - New: creates thread
6. `DailyPlanPromptBuilder.build_prompt()` assembles prompt
7. `LLMRepository.generate_content(prompt)` generates plan
8. `DiscordRepository.send_to_thread(thread, plan_text)` posts
9. `interaction.followup.send()` confirms to user

### Scheduled Auto-Posting

1. `tasks.loop` triggers at configured time (e.g., every morning at 7:00 JST)
2. Steps 3-8 same as manual execution
3. Log output on success/failure

### 2nd+ Execution on Same Day

- Step 5 finds existing thread → fetches existing messages
- Step 6 includes "previous plan" in prompt context
- LLM generates an updated plan considering prior context

## Thread Management

Posts to a journal channel with daily threads:

- **Channel**: Specified by `DAILY_PLAN_CHANNEL_ID` environment variable
- **Thread naming**: Configurable format, default `{date} 日報` (e.g., "2026-02-20 日報")
- **Thread behavior**: Uses `use_thread=True` flag
  - Create new thread for first run of the day
  - Append to existing thread for subsequent runs
- **Thread search**: By name matching in active + archived threads

## Configuration

### Environment Variables

```
# Required - External Services
TICKTICK_CLIENT_ID          # TickTick OAuth (existing)
TICKTICK_CLIENT_SECRET       # TickTick OAuth (existing)
TICKTICK_ACCESS_TOKEN        # TickTick OAuth (existing)
TICKTICK_REFRESH_TOKEN       # TickTick OAuth (existing)
GITHUB_TOKEN                 # GitHub Personal Access Token (new)
GITHUB_REPOS                 # "owner/repo1,owner/repo2" (new)

# Daily Plan Settings
DAILY_PLAN_CHANNEL_ID        # Journal channel Discord ID
DAILY_PLAN_THREAD_FORMAT     # Thread name format (default: "{date} 日報")
DAILY_PLAN_SCHEDULE_HOUR     # Auto-post hour (default: 7)
DAILY_PLAN_SCHEDULE_MINUTE   # Auto-post minute (default: 0)
DAILY_PLAN_LLM_MODEL         # LLM model (default: "gemini/gemini-3.1-pro-preview")
DAILY_PLAN_TIMEZONE          # Timezone (default: "Asia/Tokyo")
DAILY_PLAN_SOURCES           # Enabled sources (default: "ticktick,github")
```

### Design for Multi-User

- `DailyPlanConfigRepository` provides the interface for configuration access
- Current implementation reads from environment variables (single user)
- Future: replace with DB-backed repository for per-user configuration
- TODO(#future): Add per-user TickTick/GitHub credentials and channel preferences

## Error Handling

- **Source failure**: Skip failed source, generate plan with available data. Add note about failed source in output.
- **All sources fail**: Return error message to user.
- **Channel not found / not configured**: Error message with setup instructions.
- **Thread permission denied**: Catch Forbidden, notify user.
- **Scheduler failure**: Log only (no Discord notification to avoid noise).

## Testing

```
tests/
├── services/discord/           # New DiscordRepository methods
├── features/daily_plan/
│   ├── test_domain.py          # TaskSource adapters, PromptBuilder
│   └── test_repository.py      # DailyPlanConfigRepository
```

Focus on domain layer unit tests (adapter formatting, prompt construction). External API calls are covered by existing service tests. Cog integration tests deferred.
