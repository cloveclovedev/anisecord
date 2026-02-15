from datetime import date
from unittest.mock import patch

from bot.services.github.domain import GitHubMilestone


class TestGitHubMilestone:
    def test_creation_minimal(self):
        ms = GitHubMilestone(number=1, title="v1.0")
        assert ms.number == 1
        assert ms.title == "v1.0"
        assert ms.due_date is None
        assert ms.open_issues == 0
        assert ms.closed_issues == 0
        assert ms.state == "open"

    def test_creation_with_all_fields(self):
        ms = GitHubMilestone(
            number=2,
            title="v2.0",
            due_date=date(2026, 3, 1),
            open_issues=5,
            closed_issues=10,
            state="open",
        )
        assert ms.due_date == date(2026, 3, 1)
        assert ms.open_issues == 5
        assert ms.closed_issues == 10

    def test_frozen(self):
        ms = GitHubMilestone(number=1, title="v1.0")
        try:
            ms.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_progress_no_issues(self):
        ms = GitHubMilestone(number=1, title="v1.0", open_issues=0, closed_issues=0)
        assert ms.progress == 0.0

    def test_progress_partial(self):
        ms = GitHubMilestone(number=1, title="v1.0", open_issues=3, closed_issues=7)
        assert ms.progress == 0.7

    def test_progress_all_closed(self):
        ms = GitHubMilestone(number=1, title="v1.0", open_issues=0, closed_issues=5)
        assert ms.progress == 1.0

    @patch("bot.services.github.domain._today")
    def test_is_overdue_no_due_date(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=None)
        assert ms.is_overdue is False

    @patch("bot.services.github.domain._today")
    def test_is_overdue_future(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=date(2026, 3, 1))
        assert ms.is_overdue is False

    @patch("bot.services.github.domain._today")
    def test_is_overdue_past(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=date(2026, 2, 10))
        assert ms.is_overdue is True

    @patch("bot.services.github.domain._today")
    def test_is_overdue_today(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        ms = GitHubMilestone(number=1, title="v1.0", due_date=date(2026, 2, 15))
        assert ms.is_overdue is False
