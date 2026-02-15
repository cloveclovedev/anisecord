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
