from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Protocol
from zoneinfo import ZoneInfo

from bot.services.github.domain import GitHubIssue
from bot.services.google_calendar.domain import GoogleCalendarEvent
from bot.services.ticktick.domain import SubTaskStatus, TickTickTask

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


@dataclass(frozen=True)
class ContextSourceResult:
    """Result from a context source: schedule/constraint info for LLM."""

    source_name: str
    prompt_section: str


class ContextSource(Protocol):
    """Protocol for pluggable context data sources (schedule, constraints)."""

    @property
    def source_name(self) -> str: ...

    async def fetch_and_format(self) -> ContextSourceResult: ...


class TickTickTaskSource:
    """Adapter: TickTickRepository -> TaskSource."""

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
            parts.append(f"  Priority: {task.priority.name}")
            if task.project_name:
                parts.append(f"  Project: {task.project_name}")
            if task.due_date:
                parts.append(f"  Due: {task.due_date.strftime('%Y-%m-%d')}")
            if task.is_overdue:
                parts.append("  ⚠ OVERDUE")
            if task.sub_tasks:
                completed = sum(
                    1 for s in task.sub_tasks if s.status == SubTaskStatus.COMPLETED
                )
                total = len(task.sub_tasks)
                parts.append(f"  Sub-tasks: {completed}/{total} completed")
                for sub in task.sub_tasks:
                    mark = "x" if sub.status == SubTaskStatus.COMPLETED else " "
                    parts.append(f"    - [{mark}] {sub.title}")
            if task.tags:
                parts.append(f"  Tags: {', '.join(task.tags)}")
            if task.content:
                parts.append(f"  Notes: {task.content}")
            lines.append("\n".join(parts))

        return TaskSourceResult(
            source_name="ticktick",
            prompt_section="\n\n".join(lines),
            item_count=len(tasks),
        )


class GitHubTaskSource:
    """Adapter: GitHubRepository -> TaskSource."""

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
            if issue.url:
                parts.append(f"  URL: {issue.url}")
            if issue.labels:
                parts.append(f"  Labels: {', '.join(issue.labels)}")
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


class GoogleCalendarContextSource:
    """Adapter: GoogleCalendarRepository -> ContextSource."""

    def __init__(
        self,
        repository,
        calendar_context: str,
        timezone: str,
        today: date | None = None,
    ):
        self._repo = repository
        self._calendar_context = calendar_context
        self._timezone = timezone
        self._today = today

    @property
    def source_name(self) -> str:
        return "google_calendar"

    async def fetch_and_format(self) -> ContextSourceResult:
        tz = ZoneInfo(self._timezone)
        today = self._today or datetime.now(tz).date()

        # Calculate time range: start of today to end of Sunday
        time_min = datetime(today.year, today.month, today.day, tzinfo=tz)
        days_until_sunday = 6 - today.weekday()  # Monday=0, Sunday=6
        if days_until_sunday == 0:
            days_until_sunday = 7  # If today is Sunday, get next week
        end_date = today + timedelta(days=days_until_sunday + 1)
        time_max = datetime(end_date.year, end_date.month, end_date.day, tzinfo=tz)

        events = await self._repo.fetch_events(time_min=time_min, time_max=time_max)
        return self._format_events(events, today, tz)

    def _format_events(
        self,
        events: list[GoogleCalendarEvent],
        today: date,
        tz: ZoneInfo,
    ) -> ContextSourceResult:
        today_events = []
        week_events: dict[date, list[GoogleCalendarEvent]] = {}

        for event in events:
            event_date = (
                event.start.astimezone(tz).date()
                if not event.is_all_day
                else event.start.date()
            )
            if event_date == today:
                today_events.append(event)
            else:
                week_events.setdefault(event_date, []).append(event)

        # Sort events by start time within each group
        today_events.sort(key=lambda e: e.start)
        for d in week_events:
            week_events[d].sort(key=lambda e: e.start)

        lines: list[str] = []

        # Today's schedule (detailed)
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        weekday = weekday_names[today.weekday()]
        lines.append(f"## 今日のスケジュール ({today.isoformat()} {weekday}曜日)")
        if today_events:
            for event in today_events:
                lines.append(self._format_event_line(event, tz))
        else:
            lines.append("予定なし")

        # Rest of week (overview)
        if week_events:
            lines.append("")
            lines.append("## 今週の残りのスケジュール概要")
            for event_date in sorted(week_events.keys()):
                weekday = weekday_names[event_date.weekday()]
                lines.append(f"### {event_date.month}/{event_date.day} ({weekday})")
                for event in week_events[event_date]:
                    lines.append(self._format_event_line(event, tz))

        # Calendar context (interpretation rules)
        if self._calendar_context:
            lines.append("")
            lines.append("## カレンダーの解釈ルール")
            lines.append(self._calendar_context.strip())

        return ContextSourceResult(
            source_name="google_calendar",
            prompt_section="\n".join(lines),
        )

    @staticmethod
    def _format_event_line(event: GoogleCalendarEvent, tz: ZoneInfo) -> str:
        cal_name = event.calendar.summary
        if event.is_all_day:
            return f"- 終日 [{cal_name}] {event.summary}"
        start = event.start.astimezone(tz)
        end = event.end.astimezone(tz)
        return f"- {start.strftime('%H:%M')}-{end.strftime('%H:%M')} [{cal_name}] {event.summary}"


class DailyPlanPromptBuilder:
    """Assembles the final LLM prompt from task and context source sections."""

    @staticmethod
    def build_prompt(
        sections: list[TaskSourceResult],
        date_str: str,
        existing_messages: Optional[list[str]] = None,
        language: str = "ja",
        context_sections: Optional[list[ContextSourceResult]] = None,
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

        # Context sections (schedule/constraints) come first
        if context_sections:
            prompt_parts.append(
                "以下のスケジュールとカレンダー解釈ルールを考慮して、実現可能な計画を立ててください。"
            )
            prompt_parts.append(
                "空き時間を把握し、タスクを現実的にスケジュールしてください。"
            )
            prompt_parts.append("")
            prompt_parts.append("--- Schedule Context ---")
            for ctx in context_sections:
                prompt_parts.append(ctx.prompt_section)
                prompt_parts.append("")
            prompt_parts.append("--- End of Schedule Context ---")
            prompt_parts.append("")

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

        active_sections = [s for s in sections if s.item_count > 0]
        if active_sections:
            prompt_parts.append("--- Task Data ---")
            for section in active_sections:
                prompt_parts.append(section.prompt_section)
                prompt_parts.append("")
            prompt_parts.append("--- End of Task Data ---")
        else:
            prompt_parts.append(
                "No tasks found from any source. Create a general plan for the day."
            )

        prompt_parts.append("")
        prompt_parts.append("Output a well-structured daily plan in markdown format.")

        return "\n".join(prompt_parts)
