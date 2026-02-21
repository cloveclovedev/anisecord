# /daily-plan Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `/daily-plan` command that aggregates TickTick/GitHub tasks, generates a structured daily plan via LLM, and posts it to a Discord journal thread.

**Architecture:** Feature follows the existing cog/domain/repository pattern. TaskSource protocol abstracts data sources with rich text formatting. Discord service extended with thread management. Cog orchestrates: fetch from sources → build prompt → LLM generate → post to thread.

**Tech Stack:** discord.py (commands + tasks.loop), litellm (Gemini 3.1 Pro), aiohttp (TickTick/GitHub APIs), Python 3.13 Protocol typing.

---

### Task 1: Extend User model with daily-plan feature access

**Files:**
- Modify: `bot/core/user/domain.py:9-12`

**Step 1: Add "daily-plan" to the default allowed_features tuple**

```python
# bot/core/user/domain.py — change the allowed_features default
allowed_features: tuple[str, ...] = (
    "sns-x",
    "nutrition",
    "daily-plan",
)  # Default enabled for now
```

**Step 2: Verify no tests break**

Run: `uv run pytest -v`
Expected: All existing tests PASS

**Step 3: Commit**

```bash
git add bot/core/user/domain.py
git commit -m "feat(user): enable daily-plan feature access"
```

---

### Task 2: Extend Discord service with thread management

**Files:**
- Modify: `bot/services/discord/repository.py`
- Create: `tests/services/discord/__init__.py`
- Create: `tests/services/discord/test_repository.py`

**Step 1: Write failing tests for the three new methods**

Create `tests/services/discord/__init__.py` (empty).

Create `tests/services/discord/test_repository.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from bot.services.discord.repository import DiscordRepository


class TestFindOrCreateThread:
    async def test_returns_existing_thread_when_name_matches(self):
        repo = DiscordRepository()
        channel = MagicMock(spec=discord.TextChannel)

        existing_thread = MagicMock(spec=discord.Thread)
        existing_thread.name = "2026-02-20 日報"
        existing_thread.archived = False
        channel.threads = [existing_thread]

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")
        assert result == existing_thread
        channel.create_thread.assert_not_called()

    async def test_creates_new_thread_when_not_found(self):
        repo = DiscordRepository()
        channel = MagicMock(spec=discord.TextChannel)
        channel.threads = []

        # Mock archived_threads to return empty
        async def empty_archived(*args, **kwargs):
            return
            yield  # make it an async generator
        channel.archived_threads = MagicMock(return_value=empty_archived())

        new_thread = MagicMock(spec=discord.Thread)
        new_thread.name = "2026-02-20 日報"
        channel.create_thread = AsyncMock(return_value=new_thread)

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")
        assert result == new_thread
        channel.create_thread.assert_called_once_with(
            name="2026-02-20 日報",
            type=discord.ChannelType.public_thread,
        )

    async def test_finds_archived_thread(self):
        repo = DiscordRepository()
        channel = MagicMock(spec=discord.TextChannel)
        channel.threads = []  # No active threads

        archived_thread = MagicMock(spec=discord.Thread)
        archived_thread.name = "2026-02-20 日報"
        archived_thread.archived = True
        archived_thread.edit = AsyncMock()

        async def mock_archived_threads(**kwargs):
            yield archived_thread
        channel.archived_threads = lambda **kwargs: mock_archived_threads(**kwargs)

        result = await repo.find_or_create_thread(channel, "2026-02-20 日報")
        assert result == archived_thread


class TestFetchThreadMessages:
    async def test_returns_messages_as_strings(self):
        repo = DiscordRepository()
        thread = MagicMock(spec=discord.Thread)

        msg1 = MagicMock(spec=discord.Message)
        msg1.content = "今日のプラン: タスクA"
        msg1.author = MagicMock()
        msg1.author.bot = True

        msg2 = MagicMock(spec=discord.Message)
        msg2.content = "手動メモ"
        msg2.author = MagicMock()
        msg2.author.bot = False

        async def mock_history(**kwargs):
            for msg in [msg1, msg2]:
                yield msg
        thread.history = mock_history

        result = await repo.fetch_thread_messages(thread, limit=100)
        # Should include all messages (both bot and human)
        assert len(result) == 2
        assert result[0] == "今日のプラン: タスクA"
        assert result[1] == "手動メモ"


class TestSendToThread:
    async def test_sends_message_to_thread(self):
        repo = DiscordRepository()
        thread = MagicMock(spec=discord.Thread)
        thread.send = AsyncMock()

        await repo.send_to_thread(thread, "今日のプラン")
        thread.send.assert_called_once_with("今日のプラン")

    async def test_splits_long_message(self):
        repo = DiscordRepository()
        thread = MagicMock(spec=discord.Thread)
        thread.send = AsyncMock()

        long_message = "x" * 2500
        await repo.send_to_thread(thread, long_message)
        # Should be called multiple times for messages over 2000 chars
        assert thread.send.call_count >= 2
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/services/discord/test_repository.py -v`
Expected: FAIL (methods don't exist yet)

**Step 3: Implement the three new methods**

Add to `bot/services/discord/repository.py`:

```python
# Add imports at top:
# from typing import List, Optional  (already exists)
# import discord  (already exists)

class DiscordRepository:
    # ... existing fetch_messages and _to_discord_post methods ...

    async def find_or_create_thread(
        self,
        channel: discord.TextChannel,
        thread_name: str,
    ) -> discord.Thread:
        """Find an existing thread by name, or create a new one."""
        # Check active threads
        for thread in channel.threads:
            if thread.name == thread_name:
                return thread

        # Check archived threads
        try:
            async for thread in channel.archived_threads(limit=50):
                if thread.name == thread_name:
                    if thread.archived:
                        await thread.edit(archived=False)
                    return thread
        except Exception:
            pass

        # Create new thread
        return await channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
        )

    async def fetch_thread_messages(
        self,
        thread: discord.Thread,
        limit: int = 100,
    ) -> list[str]:
        """Fetch message contents from a thread."""
        messages = []
        async for msg in thread.history(limit=limit, oldest_first=True):
            messages.append(msg.content)
        return messages

    async def send_to_thread(
        self,
        thread: discord.Thread,
        content: str,
    ) -> None:
        """Send a message to a thread, splitting if over Discord's 2000 char limit."""
        if len(content) <= 2000:
            await thread.send(content)
            return

        # Split on newlines, respecting the 2000 char limit
        chunks = []
        current = ""
        for line in content.split("\n"):
            if len(current) + len(line) + 1 > 1990:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = f"{current}\n{line}" if current else line
        if current:
            chunks.append(current)

        for chunk in chunks:
            await thread.send(chunk)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/services/discord/test_repository.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: All PASS

**Step 6: Lint**

Run: `uv run ruff check . && uv run ruff format .`

**Step 7: Commit**

```bash
git add bot/services/discord/repository.py tests/services/discord/
git commit -m "feat(discord): add thread management methods to DiscordRepository"
```

---

### Task 3: Create DailyPlanConfigRepository

**Files:**
- Create: `bot/features/daily_plan/__init__.py`
- Create: `bot/features/daily_plan/repository.py`
- Create: `tests/features/__init__.py`
- Create: `tests/features/daily_plan/__init__.py`
- Create: `tests/features/daily_plan/test_repository.py`

**Step 1: Write failing tests**

Create all `__init__.py` files (empty).

Create `tests/features/daily_plan/test_repository.py`:

```python
import os
from unittest.mock import patch

from bot.features.daily_plan.repository import DailyPlanConfig, DailyPlanConfigRepository


class TestDailyPlanConfigRepository:
    def test_loads_defaults_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.channel_id is None
        assert config.thread_format == "{date} 日報"
        assert config.schedule_hour == 7
        assert config.schedule_minute == 0
        assert config.llm_model == "gemini/gemini-3.1-pro-preview"
        assert config.timezone == "Asia/Tokyo"
        assert config.sources == ("ticktick", "github")

    def test_loads_from_env_vars(self):
        env = {
            "DAILY_PLAN_CHANNEL_ID": "123456789",
            "DAILY_PLAN_THREAD_FORMAT": "{date} daily",
            "DAILY_PLAN_SCHEDULE_HOUR": "9",
            "DAILY_PLAN_SCHEDULE_MINUTE": "30",
            "DAILY_PLAN_LLM_MODEL": "gemini/gemini-2.5-flash",
            "DAILY_PLAN_TIMEZONE": "US/Eastern",
            "DAILY_PLAN_SOURCES": "ticktick",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.channel_id == 123456789
        assert config.thread_format == "{date} daily"
        assert config.schedule_hour == 9
        assert config.schedule_minute == 30
        assert config.llm_model == "gemini/gemini-2.5-flash"
        assert config.timezone == "US/Eastern"
        assert config.sources == ("ticktick",)

    def test_ticktick_config_from_env(self):
        env = {
            "TICKTICK_CLIENT_ID": "cid",
            "TICKTICK_CLIENT_SECRET": "csec",
            "TICKTICK_ACCESS_TOKEN": "at",
            "TICKTICK_REFRESH_TOKEN": "rt",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.ticktick_client_id == "cid"
        assert config.ticktick_client_secret == "csec"
        assert config.ticktick_access_token == "at"
        assert config.ticktick_refresh_token == "rt"

    def test_github_config_from_env(self):
        env = {
            "GITHUB_TOKEN": "ghp_xxx",
            "GITHUB_REPOS": "owner/repo1,owner/repo2",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.github_token == "ghp_xxx"
        assert config.github_repos == ["owner/repo1", "owner/repo2"]

    def test_has_source_checks_sources_and_credentials(self):
        env = {
            "DAILY_PLAN_SOURCES": "ticktick,github",
            "TICKTICK_CLIENT_ID": "cid",
            "TICKTICK_CLIENT_SECRET": "csec",
            "TICKTICK_ACCESS_TOKEN": "at",
            "TICKTICK_REFRESH_TOKEN": "rt",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.has_source("ticktick") is True
        assert config.has_source("github") is False  # no GITHUB_TOKEN


class TestDailyPlanConfig:
    def test_frozen(self):
        config = DailyPlanConfig()
        try:
            config.timezone = "US/Pacific"
            assert False, "Should be frozen"
        except AttributeError:
            pass
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/features/daily_plan/test_repository.py -v`
Expected: FAIL (module doesn't exist)

**Step 3: Implement**

Create `bot/features/daily_plan/__init__.py` (empty).

Create `bot/features/daily_plan/repository.py`:

```python
import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DailyPlanConfig:
    """Configuration for the daily-plan feature.

    Currently reads from environment variables.
    TODO(#future): Replace with DB-backed per-user configuration for multi-user support.
    """

    channel_id: Optional[int] = None
    thread_format: str = "{date} 日報"
    schedule_hour: int = 7
    schedule_minute: int = 0
    llm_model: str = "gemini/gemini-3.1-pro-preview"
    timezone: str = "Asia/Tokyo"
    sources: tuple[str, ...] = ("ticktick", "github")

    # TickTick credentials
    ticktick_client_id: str = ""
    ticktick_client_secret: str = ""
    ticktick_access_token: str = ""
    ticktick_refresh_token: str = ""

    # GitHub credentials
    github_token: str = ""
    github_repos: list[str] | None = None

    def has_source(self, source_name: str) -> bool:
        """Check if a source is enabled AND has valid credentials."""
        if source_name not in self.sources:
            return False
        if source_name == "ticktick":
            return bool(self.ticktick_access_token)
        if source_name == "github":
            return bool(self.github_token and self.github_repos)
        return False


class DailyPlanConfigRepository:
    """Loads daily-plan configuration.

    Currently reads from environment variables.
    TODO(#future): Replace with DB fetch for per-user settings.
    """

    def get_config(self) -> DailyPlanConfig:
        channel_id_str = os.environ.get("DAILY_PLAN_CHANNEL_ID")
        sources_str = os.environ.get("DAILY_PLAN_SOURCES", "ticktick,github")
        github_repos_str = os.environ.get("GITHUB_REPOS", "")

        return DailyPlanConfig(
            channel_id=int(channel_id_str) if channel_id_str else None,
            thread_format=os.environ.get("DAILY_PLAN_THREAD_FORMAT", "{date} 日報"),
            schedule_hour=int(os.environ.get("DAILY_PLAN_SCHEDULE_HOUR", "7")),
            schedule_minute=int(os.environ.get("DAILY_PLAN_SCHEDULE_MINUTE", "0")),
            llm_model=os.environ.get(
                "DAILY_PLAN_LLM_MODEL", "gemini/gemini-3.1-pro-preview"
            ),
            timezone=os.environ.get("DAILY_PLAN_TIMEZONE", "Asia/Tokyo"),
            sources=tuple(s.strip() for s in sources_str.split(",") if s.strip()),
            ticktick_client_id=os.environ.get("TICKTICK_CLIENT_ID", ""),
            ticktick_client_secret=os.environ.get("TICKTICK_CLIENT_SECRET", ""),
            ticktick_access_token=os.environ.get("TICKTICK_ACCESS_TOKEN", ""),
            ticktick_refresh_token=os.environ.get("TICKTICK_REFRESH_TOKEN", ""),
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            github_repos=(
                [r.strip() for r in github_repos_str.split(",") if r.strip()]
                if github_repos_str
                else None
            ),
        )
```

Note: `github_repos` is a `list` on a frozen dataclass. This works in Python but the list itself is mutable — acceptable for a config object that is read-only in practice. If strict immutability is desired, change to `tuple[str, ...] | None`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/features/daily_plan/test_repository.py -v`
Expected: PASS

**Step 5: Lint**

Run: `uv run ruff check . && uv run ruff format .`

**Step 6: Commit**

```bash
git add bot/features/daily_plan/__init__.py bot/features/daily_plan/repository.py \
       tests/features/__init__.py tests/features/daily_plan/__init__.py \
       tests/features/daily_plan/test_repository.py
git commit -m "feat(daily-plan): add DailyPlanConfigRepository with env var config"
```

---

### Task 4: Create domain layer — TaskSource protocol and adapters

**Files:**
- Create: `bot/features/daily_plan/domain.py`
- Create: `tests/features/daily_plan/test_domain.py`

**Step 1: Write failing tests**

Create `tests/features/daily_plan/test_domain.py`:

```python
from datetime import datetime, date
from zoneinfo import ZoneInfo

from bot.services.ticktick.domain import (
    TickTickTask,
    TickTickSubTask,
    TaskStatus,
    TaskPriority,
    SubTaskStatus,
)
from bot.services.github.domain import GitHubIssue, GitHubMilestone
from bot.features.daily_plan.domain import (
    TaskSourceResult,
    TickTickTaskSource,
    GitHubTaskSource,
    DailyPlanPromptBuilder,
)


class TestTaskSourceResult:
    def test_creation(self):
        result = TaskSourceResult(
            source_name="test",
            prompt_section="some text",
            item_count=3,
        )
        assert result.source_name == "test"
        assert result.prompt_section == "some text"
        assert result.item_count == 3

    def test_frozen(self):
        result = TaskSourceResult(
            source_name="test", prompt_section="text", item_count=1
        )
        try:
            result.source_name = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestTickTickTaskSource:
    def _make_task(self, **overrides) -> TickTickTask:
        defaults = dict(
            id="t1",
            title="Test task",
            project_id="p1",
            project_name="Work",
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.HIGH,
            is_overdue=False,
        )
        defaults.update(overrides)
        return TickTickTask(**defaults)

    async def test_source_name(self):
        source = TickTickTaskSource(repo=None)
        assert source.source_name == "ticktick"

    async def test_format_includes_task_title(self):
        task = self._make_task(title="Deploy app")
        result = TickTickTaskSource.format_tasks([task])
        assert "Deploy app" in result.prompt_section
        assert result.item_count == 1

    async def test_format_includes_priority(self):
        task = self._make_task(priority=TaskPriority.HIGH)
        result = TickTickTaskSource.format_tasks([task])
        assert "HIGH" in result.prompt_section or "高" in result.prompt_section

    async def test_format_includes_overdue_flag(self):
        task = self._make_task(is_overdue=True, title="Overdue task")
        result = TickTickTaskSource.format_tasks([task])
        assert "overdue" in result.prompt_section.lower() or "期限切れ" in result.prompt_section

    async def test_format_includes_subtask_progress(self):
        subs = (
            TickTickSubTask(title="Step 1", status=SubTaskStatus.COMPLETED, sort_order=0),
            TickTickSubTask(title="Step 2", status=SubTaskStatus.ACTIVE, sort_order=1),
            TickTickSubTask(title="Step 3", status=SubTaskStatus.ACTIVE, sort_order=2),
        )
        task = self._make_task(sub_tasks=subs)
        result = TickTickTaskSource.format_tasks([task])
        assert "1/3" in result.prompt_section

    async def test_format_includes_project_name(self):
        task = self._make_task(project_name="My Project")
        result = TickTickTaskSource.format_tasks([task])
        assert "My Project" in result.prompt_section

    async def test_format_empty_returns_zero_count(self):
        result = TickTickTaskSource.format_tasks([])
        assert result.item_count == 0

    async def test_format_includes_due_date(self):
        task = self._make_task(
            due_date=datetime(2026, 2, 20, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        )
        result = TickTickTaskSource.format_tasks([task])
        assert "2026-02-20" in result.prompt_section


class TestGitHubTaskSource:
    def _make_issue(self, **overrides) -> GitHubIssue:
        defaults = dict(
            number=42,
            title="Fix bug",
            repo="owner/repo",
            state="open",
            url="https://github.com/owner/repo/issues/42",
        )
        defaults.update(overrides)
        return GitHubIssue(**defaults)

    def _make_milestone(self, **overrides) -> GitHubMilestone:
        defaults = dict(
            number=1,
            title="v1.0",
            open_issues=3,
            closed_issues=7,
        )
        defaults.update(overrides)
        return GitHubMilestone(**defaults)

    async def test_source_name(self):
        source = GitHubTaskSource(repo=None)
        assert source.source_name == "github"

    async def test_format_includes_issue_title(self):
        issue = self._make_issue(title="Add authentication")
        result = GitHubTaskSource.format_issues([issue])
        assert "Add authentication" in result.prompt_section
        assert result.item_count == 1

    async def test_format_includes_repo_and_number(self):
        issue = self._make_issue(repo="mkuri/anisecord", number=39)
        result = GitHubTaskSource.format_issues([issue])
        assert "mkuri/anisecord" in result.prompt_section
        assert "#39" in result.prompt_section

    async def test_format_includes_milestone_progress(self):
        ms = self._make_milestone(open_issues=2, closed_issues=8)
        issue = self._make_issue(milestone=ms)
        result = GitHubTaskSource.format_issues([issue])
        # 8/(8+2) = 80%
        assert "80%" in result.prompt_section

    async def test_format_includes_labels(self):
        issue = self._make_issue(labels=("bug", "urgent"))
        result = GitHubTaskSource.format_issues([issue])
        assert "bug" in result.prompt_section
        assert "urgent" in result.prompt_section

    async def test_format_includes_url(self):
        issue = self._make_issue(url="https://github.com/owner/repo/issues/42")
        result = GitHubTaskSource.format_issues([issue])
        assert "https://github.com/owner/repo/issues/42" in result.prompt_section

    async def test_format_empty_returns_zero_count(self):
        result = GitHubTaskSource.format_issues([])
        assert result.item_count == 0


class TestDailyPlanPromptBuilder:
    def test_build_prompt_combines_sections(self):
        sections = [
            TaskSourceResult(source_name="ticktick", prompt_section="## TickTick\n- Task A", item_count=1),
            TaskSourceResult(source_name="github", prompt_section="## GitHub\n- Issue B", item_count=1),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str="2026-02-20",
        )
        assert "TickTick" in prompt
        assert "GitHub" in prompt
        assert "Task A" in prompt
        assert "Issue B" in prompt
        assert "2026-02-20" in prompt

    def test_build_prompt_includes_existing_messages(self):
        sections = [
            TaskSourceResult(source_name="ticktick", prompt_section="## TickTick\n- Task A", item_count=1),
        ]
        existing = ["前回のプラン: タスクAに集中する", "14:00 タスクA完了"]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str="2026-02-20",
            existing_messages=existing,
        )
        assert "前回のプラン" in prompt
        assert "タスクA完了" in prompt

    def test_build_prompt_without_existing_messages(self):
        sections = [
            TaskSourceResult(source_name="ticktick", prompt_section="## TickTick\n- Task A", item_count=1),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str="2026-02-20",
        )
        # Should not contain "previous" context sections
        assert "前回" not in prompt or "既存" not in prompt

    def test_build_prompt_respects_language(self):
        sections = [
            TaskSourceResult(source_name="test", prompt_section="- Task", item_count=1),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str="2026-02-20",
            language="en",
        )
        assert "en" in prompt.lower() or "english" in prompt.lower()

    def test_build_prompt_handles_all_empty_sources(self):
        sections = [
            TaskSourceResult(source_name="ticktick", prompt_section="", item_count=0),
            TaskSourceResult(source_name="github", prompt_section="", item_count=0),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str="2026-02-20",
        )
        # Should still produce a valid prompt
        assert "2026-02-20" in prompt
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/features/daily_plan/test_domain.py -v`
Expected: FAIL (module doesn't exist)

**Step 3: Implement domain.py**

Create `bot/features/daily_plan/domain.py`:

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from bot.services.ticktick.domain import (
    SubTaskStatus,
    TickTickTask,
)
from bot.services.github.domain import GitHubIssue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskSourceResult:
    """Result from a task source: rich prompt section text + metadata."""

    source_name: str
    prompt_section: str
    item_count: int


class TaskSource(Protocol):
    """Protocol for pluggable task data sources."""

    @property
    def source_name(self) -> str: ...

    async def fetch_and_format(self) -> TaskSourceResult: ...


class TickTickTaskSource:
    """Adapter: TickTickRepository → TaskSource."""

    def __init__(self, repo):
        self._repo = repo

    @property
    def source_name(self) -> str:
        return "ticktick"

    async def fetch_and_format(self) -> TaskSourceResult:
        tasks = await self._repo.fetch_actionable_tasks()
        return self.format_tasks(tasks)

    @staticmethod
    def format_tasks(tasks: list[TickTickTask]) -> TaskSourceResult:
        if not tasks:
            return TaskSourceResult(
                source_name="ticktick", prompt_section="", item_count=0
            )

        lines = ["## TickTick Tasks"]
        for task in tasks:
            parts = [f"- **{task.title}**"]

            # Priority
            priority_name = task.priority.name
            parts.append(f"  Priority: {priority_name}")

            # Project
            if task.project_name:
                parts.append(f"  Project: {task.project_name}")

            # Due date
            if task.due_date:
                parts.append(f"  Due: {task.due_date.strftime('%Y-%m-%d')}")

            # Overdue
            if task.is_overdue:
                parts.append("  ⚠ OVERDUE")

            # Sub-task progress
            if task.sub_tasks:
                completed = sum(
                    1 for s in task.sub_tasks if s.status == SubTaskStatus.COMPLETED
                )
                total = len(task.sub_tasks)
                parts.append(f"  Sub-tasks: {completed}/{total} completed")
                for sub in task.sub_tasks:
                    mark = "x" if sub.status == SubTaskStatus.COMPLETED else " "
                    parts.append(f"    - [{mark}] {sub.title}")

            # Tags
            if task.tags:
                parts.append(f"  Tags: {', '.join(task.tags)}")

            # Notes
            if task.content:
                parts.append(f"  Notes: {task.content}")

            lines.append("\n".join(parts))

        return TaskSourceResult(
            source_name="ticktick",
            prompt_section="\n\n".join(lines),
            item_count=len(tasks),
        )


class GitHubTaskSource:
    """Adapter: GitHubRepository → TaskSource."""

    def __init__(self, repo):
        self._repo = repo

    @property
    def source_name(self) -> str:
        return "github"

    async def fetch_and_format(self) -> TaskSourceResult:
        issues = await self._repo.fetch_actionable_issues()
        return self.format_issues(issues)

    @staticmethod
    def format_issues(issues: list[GitHubIssue]) -> TaskSourceResult:
        if not issues:
            return TaskSourceResult(
                source_name="github", prompt_section="", item_count=0
            )

        lines = ["## GitHub Issues"]
        for issue in issues:
            parts = [f"- **{issue.repo}#{issue.number}: {issue.title}**"]

            # URL
            if issue.url:
                parts.append(f"  URL: {issue.url}")

            # Labels
            if issue.labels:
                parts.append(f"  Labels: {', '.join(issue.labels)}")

            # Milestone
            if issue.milestone:
                ms = issue.milestone
                progress_pct = int(ms.progress * 100)
                ms_info = f"  Milestone: {ms.title} ({progress_pct}% complete)"
                if ms.due_date:
                    ms_info += f", due {ms.due_date}"
                if ms.is_overdue:
                    ms_info += " ⚠ OVERDUE"
                parts.append(ms_info)

            lines.append("\n".join(parts))

        return TaskSourceResult(
            source_name="github",
            prompt_section="\n\n".join(lines),
            item_count=len(issues),
        )


class DailyPlanPromptBuilder:
    """Assembles the final LLM prompt from task source sections."""

    @staticmethod
    def build_prompt(
        sections: list[TaskSourceResult],
        date_str: str,
        existing_messages: Optional[list[str]] = None,
        language: str = "ja",
    ) -> str:
        prompt_parts = [
            f"You are a personal productivity assistant. Create a structured daily plan for {date_str}.",
            f"Write the plan in {language} (language code).",
            "",
            "Based on the following tasks from various sources, create a prioritized daily plan.",
            "Consider urgency, deadlines, overdue status, and dependencies when prioritizing.",
            "Group related tasks and suggest a logical order for the day.",
            "",
        ]

        # Add existing thread context for 2nd+ runs
        if existing_messages:
            prompt_parts.append("--- Previous messages in today's thread ---")
            for msg in existing_messages:
                prompt_parts.append(msg)
            prompt_parts.append("--- End of previous messages ---")
            prompt_parts.append("")
            prompt_parts.append(
                "Consider the above context. This is a follow-up plan update. "
                "Note any progress or changes from the earlier plan."
            )
            prompt_parts.append("")

        # Add each source section
        active_sections = [s for s in sections if s.item_count > 0]
        if active_sections:
            prompt_parts.append("--- Task Data ---")
            for section in active_sections:
                prompt_parts.append(section.prompt_section)
                prompt_parts.append("")
            prompt_parts.append("--- End of Task Data ---")
        else:
            prompt_parts.append("No tasks found from any source. Create a general plan for the day.")

        prompt_parts.append("")
        prompt_parts.append("Output a well-structured daily plan in markdown format.")

        return "\n".join(prompt_parts)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/features/daily_plan/test_domain.py -v`
Expected: PASS

**Step 5: Lint**

Run: `uv run ruff check . && uv run ruff format .`

**Step 6: Commit**

```bash
git add bot/features/daily_plan/domain.py tests/features/daily_plan/test_domain.py
git commit -m "feat(daily-plan): add TaskSource protocol, adapters, and prompt builder"
```

---

### Task 5: Create the Cog — /daily-plan command

**Files:**
- Create: `bot/features/daily_plan/cog.py`
- Modify: `bot/core/bot.py:36-39`

**Step 1: Implement the cog**

Create `bot/features/daily_plan/cog.py`:

```python
import asyncio
import datetime
import logging
from zoneinfo import ZoneInfo

import discord
from discord import Interaction, app_commands
from discord.ext import commands, tasks

from bot.core.user.decorators import feature_enabled
from bot.core.user.repository import UserRepository
from bot.services.discord.repository import DiscordRepository
from bot.services.github.repository import GitHubRepository
from bot.services.llm.repository import LLMRepository
from bot.services.ticktick.auth import TickTickAuth
from bot.services.ticktick.repository import TickTickRepository

from .domain import (
    DailyPlanPromptBuilder,
    GitHubTaskSource,
    TaskSource,
    TickTickTaskSource,
)
from .repository import DailyPlanConfigRepository

logger = logging.getLogger(__name__)


class DailyPlanCog(commands.Cog):
    """Generate and post daily plans from external task sources."""

    def __init__(self, bot):
        self.bot = bot
        self.config_repo = DailyPlanConfigRepository()
        self.discord_repo = DiscordRepository()
        self.user_repo = UserRepository()

        # Load config once at init
        self._config = self.config_repo.get_config()

        # LLM with configurable model
        self.llm_repo = LLMRepository(
            model_name=self._config.llm_model,
            api_key=self.bot.gemini_api_key,
        )

        # Build task sources based on config
        self._sources: list[TaskSource] = []
        self._init_sources()

    def _init_sources(self) -> None:
        """Initialize enabled task sources."""
        if self._config.has_source("ticktick"):
            auth = TickTickAuth(
                client_id=self._config.ticktick_client_id,
                client_secret=self._config.ticktick_client_secret,
                access_token=self._config.ticktick_access_token,
                refresh_token=self._config.ticktick_refresh_token,
            )
            self._sources.append(TickTickTaskSource(TickTickRepository(auth)))

        if self._config.has_source("github"):
            self._sources.append(
                GitHubTaskSource(
                    GitHubRepository(
                        token=self._config.github_token,
                        repos=self._config.github_repos or [],
                    )
                )
            )

    async def cog_load(self) -> None:
        """Called when the cog is loaded. Start the scheduler if configured."""
        if self._config.channel_id:
            self._schedule_loop.start()

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded. Stop the scheduler."""
        if self._schedule_loop.is_running():
            self._schedule_loop.cancel()

    @tasks.loop(time=[])  # time set dynamically in cog_load
    async def _schedule_loop(self) -> None:
        """Scheduled daily plan posting."""
        logger.info("Scheduled daily plan triggered")
        try:
            await self._generate_and_post()
        except Exception:
            logger.exception("Scheduled daily plan failed")

    @_schedule_loop.before_loop
    async def _before_schedule(self) -> None:
        """Wait until bot is ready before starting the scheduler."""
        await self.bot.wait_until_ready()

        # Set the scheduled time dynamically
        tz = ZoneInfo(self._config.timezone)
        scheduled_time = datetime.time(
            hour=self._config.schedule_hour,
            minute=self._config.schedule_minute,
            tzinfo=tz,
        )
        self._schedule_loop.change_interval(time=[scheduled_time])

    @app_commands.command(
        name="daily-plan",
        description="Generate today's plan from TickTick and GitHub tasks.",
    )
    @feature_enabled("daily-plan")
    async def daily_plan(self, interaction: Interaction) -> None:
        """Manual trigger for daily plan generation."""
        await interaction.response.defer()

        try:
            result_message = await self._generate_and_post()
            await interaction.followup.send(result_message)
        except Exception as e:
            logger.exception("Failed to generate daily plan")
            await interaction.followup.send(f"❌ Failed to generate daily plan: {e}")

    async def _generate_and_post(self) -> str:
        """Core logic: fetch tasks → build prompt → LLM → post to thread.

        Returns a status message.
        """
        config = self._config
        tz = ZoneInfo(config.timezone)
        today = datetime.datetime.now(tz).date()
        date_str = today.strftime("%Y-%m-%d")
        thread_name = config.thread_format.format(date=date_str)

        # 1. Fetch from all sources concurrently
        results = await asyncio.gather(
            *[source.fetch_and_format() for source in self._sources],
            return_exceptions=True,
        )

        # Separate successes and failures
        sections = []
        errors = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                source_name = self._sources[i].source_name
                logger.error("Source %s failed: %s", source_name, result)
                errors.append(source_name)
            else:
                sections.append(result)

        if not sections and not errors:
            return "⚠ No task sources are configured. Set DAILY_PLAN_SOURCES and credentials."

        if not sections and errors:
            return f"❌ All task sources failed: {', '.join(errors)}"

        # 2. Find or create thread
        if not config.channel_id:
            return "⚠ DAILY_PLAN_CHANNEL_ID is not configured."

        channel = self.bot.get_channel(config.channel_id)
        if channel is None:
            return f"❌ Channel {config.channel_id} not found."

        thread = await self.discord_repo.find_or_create_thread(channel, thread_name)

        # 3. Fetch existing messages for context (2nd+ run)
        existing_messages = await self.discord_repo.fetch_thread_messages(thread)

        # 4. Build prompt and generate plan
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str=date_str,
            existing_messages=existing_messages if existing_messages else None,
        )

        plan_text = await self.llm_repo.generate_content(prompt)

        # 5. Post to thread
        await self.discord_repo.send_to_thread(thread, plan_text)

        # 6. Build status message
        total_items = sum(s.item_count for s in sections)
        status = f"✅ Daily plan posted to {thread.mention} ({total_items} tasks"
        if errors:
            status += f", ⚠ failed sources: {', '.join(errors)}"
        status += ")"
        return status


async def setup(bot):
    await bot.add_cog(DailyPlanCog(bot))
```

**Step 2: Register the extension in bot.py**

Modify `bot/core/bot.py` — add `"bot.features.daily_plan.cog"` to the `oss_extensions` list:

```python
oss_extensions = [
    "bot.features.common.basic_commands",
    "bot.features.nutrition.cog",
    "bot.features.sns_x.cog",
    "bot.features.daily_plan.cog",
]
```

**Step 3: Verify all tests still pass**

Run: `uv run pytest -v`
Expected: All PASS

**Step 4: Lint**

Run: `uv run ruff check . && uv run ruff format .`

**Step 5: Commit**

```bash
git add bot/features/daily_plan/cog.py bot/core/bot.py
git commit -m "feat(daily-plan): add /daily-plan command with scheduled auto-posting"
```

---

### Task 6: Integration verification and cleanup

**Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

**Step 2: Run linter**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: No issues

**Step 3: Verify .env.example or documentation**

Check if there's a `.env.example` or similar. If so, add the new environment variables. If not, skip.

Run: `ls -la .env*` to check.

**Step 4: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore(daily-plan): cleanup and lint fixes"
```

---

## Summary

| Task | Description | Tests |
|------|------------|-------|
| 1 | Enable daily-plan feature access in User model | Existing tests |
| 2 | Extend Discord service with thread management | `tests/services/discord/test_repository.py` |
| 3 | Create DailyPlanConfigRepository | `tests/features/daily_plan/test_repository.py` |
| 4 | Create domain layer (TaskSource, adapters, prompt builder) | `tests/features/daily_plan/test_domain.py` |
| 5 | Create Cog with command + scheduler | Manual verification |
| 6 | Integration verification and cleanup | Full test suite |

## Future Work (tracked in issues)

- TODO(#future): Per-user configuration via DB (multi-user support)
- TODO(#future): `/weekly-plan` command (Epic #35)
- TODO(#future): Customizable prompt templates per user
- TODO(#future): Plan feedback loop (user marks tasks done, bot updates)
