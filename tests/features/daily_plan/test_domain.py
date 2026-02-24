from datetime import date, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from bot.features.daily_plan.domain import (
    ContextSourceResult,
    DailyPlanPromptBuilder,
    GitHubTaskSource,
    GoogleCalendarContextSource,
    TaskSourceResult,
    TickTickTaskSource,
)
from bot.services.github.domain import GitHubIssue, GitHubMilestone
from bot.services.google_calendar.domain import GoogleCalendarEvent, GoogleCalendarInfo
from bot.services.ticktick.domain import (
    SubTaskStatus,
    TaskPriority,
    TaskStatus,
    TickTickSubTask,
    TickTickTask,
)

JST = ZoneInfo("Asia/Tokyo")


class TestTaskSourceResult:
    def test_creation(self):
        result = TaskSourceResult(
            source_name="test", prompt_section="some text", item_count=3
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
        assert "HIGH" in result.prompt_section

    async def test_format_includes_overdue_flag(self):
        task = self._make_task(is_overdue=True)
        result = TickTickTaskSource.format_tasks([task])
        assert "OVERDUE" in result.prompt_section

    async def test_format_includes_subtask_progress(self):
        subs = (
            TickTickSubTask(
                title="Step 1", status=SubTaskStatus.COMPLETED, sort_order=0
            ),
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

    async def test_format_includes_tags(self):
        task = self._make_task(tags=("urgent", "work"))
        result = TickTickTaskSource.format_tasks([task])
        assert "urgent" in result.prompt_section
        assert "work" in result.prompt_section

    async def test_format_includes_notes(self):
        task = self._make_task(content="Remember to check docs")
        result = TickTickTaskSource.format_tasks([task])
        assert "Remember to check docs" in result.prompt_section


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
        defaults = dict(number=1, title="v1.0", open_issues=3, closed_issues=7)
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

    async def test_format_includes_milestone_due_date(self):
        ms = self._make_milestone(due_date=date(2026, 3, 1))
        issue = self._make_issue(milestone=ms)
        result = GitHubTaskSource.format_issues([issue])
        assert "2026-03-01" in result.prompt_section


class TestDailyPlanPromptBuilder:
    def test_build_prompt_combines_sections(self):
        sections = [
            TaskSourceResult(
                source_name="ticktick",
                prompt_section="## TickTick\n- Task A",
                item_count=1,
            ),
            TaskSourceResult(
                source_name="github",
                prompt_section="## GitHub\n- Issue B",
                item_count=1,
            ),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections, date_str="2026-02-20"
        )
        assert "TickTick" in prompt
        assert "GitHub" in prompt
        assert "Task A" in prompt
        assert "Issue B" in prompt
        assert "2026-02-20" in prompt

    def test_build_prompt_includes_existing_messages(self):
        sections = [
            TaskSourceResult(
                source_name="ticktick",
                prompt_section="## TickTick\n- Task A",
                item_count=1,
            ),
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
            TaskSourceResult(
                source_name="ticktick",
                prompt_section="## TickTick\n- Task A",
                item_count=1,
            ),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections, date_str="2026-02-20"
        )
        assert "Previous messages" not in prompt

    def test_build_prompt_respects_language(self):
        sections = [
            TaskSourceResult(source_name="test", prompt_section="- Task", item_count=1),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str="2026-02-20",
            language="en",
        )
        assert "en" in prompt

    def test_build_prompt_handles_all_empty_sources(self):
        sections = [
            TaskSourceResult(source_name="ticktick", prompt_section="", item_count=0),
            TaskSourceResult(source_name="github", prompt_section="", item_count=0),
        ]
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections, date_str="2026-02-20"
        )
        assert "2026-02-20" in prompt
        assert "No tasks found" in prompt


class TestContextSourceResult:
    def test_creation(self):
        result = ContextSourceResult(
            source_name="google_calendar",
            prompt_section="## Schedule\n- 10:00 Meeting",
        )
        assert result.source_name == "google_calendar"
        assert result.prompt_section == "## Schedule\n- 10:00 Meeting"

    def test_frozen(self):
        result = ContextSourceResult(
            source_name="test", prompt_section="text"
        )
        try:
            result.source_name = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestGoogleCalendarContextSource:
    def _make_event(self, **overrides) -> GoogleCalendarEvent:
        defaults = dict(
            id="ev1",
            summary="Test Event",
            calendar=GoogleCalendarInfo(id="cal1", summary="Work"),
            start=datetime(2026, 2, 23, 10, 0, tzinfo=JST),
            end=datetime(2026, 2, 23, 11, 0, tzinfo=JST),
            is_all_day=False,
            location=None,
            status="confirmed",
        )
        defaults.update(overrides)
        return GoogleCalendarEvent(**defaults)

    def _make_source(
        self,
        events: list[GoogleCalendarEvent],
        calendar_context: str = "",
        today: date = date(2026, 2, 23),
    ) -> GoogleCalendarContextSource:
        repo = AsyncMock()
        repo.fetch_events.return_value = events
        return GoogleCalendarContextSource(
            repository=repo,
            calendar_context=calendar_context,
            timezone="Asia/Tokyo",
            today=today,
        )

    async def test_source_name(self):
        source = self._make_source(events=[])
        assert source.source_name == "google_calendar"

    async def test_format_includes_calendar_name(self):
        event = self._make_event(
            calendar=GoogleCalendarInfo(id="cal1", summary="cloveclove"),
        )
        source = self._make_source(events=[event])
        result = await source.fetch_and_format()
        assert "[cloveclove]" in result.prompt_section

    async def test_format_includes_event_time_and_title(self):
        event = self._make_event(
            summary="WRK | @品川",
            start=datetime(2026, 2, 23, 10, 30, tzinfo=JST),
            end=datetime(2026, 2, 23, 20, 0, tzinfo=JST),
        )
        source = self._make_source(events=[event])
        result = await source.fetch_and_format()
        assert "10:30" in result.prompt_section
        assert "20:00" in result.prompt_section
        assert "WRK | @品川" in result.prompt_section

    async def test_format_all_day_event(self):
        event = self._make_event(
            summary="Emperor's Birthday",
            is_all_day=True,
        )
        source = self._make_source(events=[event])
        result = await source.fetch_and_format()
        assert "終日" in result.prompt_section

    async def test_format_separates_today_and_rest_of_week(self):
        today_event = self._make_event(
            summary="Today Event",
            start=datetime(2026, 2, 23, 10, 0, tzinfo=JST),
            end=datetime(2026, 2, 23, 11, 0, tzinfo=JST),
        )
        tomorrow_event = self._make_event(
            id="ev2",
            summary="Tomorrow Event",
            start=datetime(2026, 2, 24, 14, 0, tzinfo=JST),
            end=datetime(2026, 2, 24, 15, 0, tzinfo=JST),
        )
        source = self._make_source(events=[today_event, tomorrow_event])
        result = await source.fetch_and_format()
        today_pos = result.prompt_section.find("Today Event")
        tomorrow_pos = result.prompt_section.find("Tomorrow Event")
        assert today_pos < tomorrow_pos

    async def test_format_includes_calendar_context(self):
        event = self._make_event()
        context = "clovecloveカレンダーは個人事業の作業時間。"
        source = self._make_source(events=[event], calendar_context=context)
        result = await source.fetch_and_format()
        assert "clovecloveカレンダーは個人事業の作業時間。" in result.prompt_section

    async def test_format_empty_events(self):
        source = self._make_source(events=[])
        result = await source.fetch_and_format()
        assert result.source_name == "google_calendar"

    async def test_fetch_passes_correct_time_range(self):
        """Verify the source requests today through end-of-week."""
        repo = AsyncMock()
        repo.fetch_events.return_value = []
        source = GoogleCalendarContextSource(
            repository=repo,
            calendar_context="",
            timezone="Asia/Tokyo",
            today=date(2026, 2, 23),  # Monday
        )
        await source.fetch_and_format()

        repo.fetch_events.assert_called_once()
        call_args = repo.fetch_events.call_args
        time_min = call_args.kwargs["time_min"]
        time_max = call_args.kwargs["time_max"]
        assert time_min.date() == date(2026, 2, 23)
        assert time_max.date() >= date(2026, 2, 28)
