from datetime import datetime
from zoneinfo import ZoneInfo

from bot.features.daily_plan.domain import (
    DailyPlanPromptBuilder,
    GitHubTaskSource,
    TaskSourceResult,
    TickTickTaskSource,
)
from bot.services.github.domain import GitHubIssue, GitHubMilestone
from bot.services.ticktick.domain import (
    SubTaskStatus,
    TaskPriority,
    TaskStatus,
    TickTickSubTask,
    TickTickTask,
)


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
        from datetime import date

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
