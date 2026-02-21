from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from bot.services.github.domain import GitHubIssue
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
