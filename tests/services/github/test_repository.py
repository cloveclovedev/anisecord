from datetime import date, datetime

from aioresponses import aioresponses

from bot.services.github.domain import GitHubIssue, GitHubMilestone
from bot.services.github.repository import GitHubRepository

API_BASE = "https://api.github.com"


def make_repo(repos: list[str] | None = None) -> GitHubRepository:
    return GitHubRepository(
        token="test_token",
        repos=repos or ["owner/repo1"],
    )


SAMPLE_MILESTONES = [
    {
        "number": 1,
        "title": "v1.0",
        "due_on": "2026-03-01T08:00:00Z",
        "open_issues": 3,
        "closed_issues": 7,
        "state": "open",
    },
    {
        "number": 2,
        "title": "v2.0",
        "due_on": None,
        "open_issues": 5,
        "closed_issues": 0,
        "state": "open",
    },
]

SAMPLE_MILESTONE_RAW = {
    "number": 1,
    "title": "v1.0",
    "due_on": "2026-03-01T08:00:00Z",
    "open_issues": 3,
    "closed_issues": 7,
    "state": "open",
}

SAMPLE_ISSUES = [
    {
        "number": 10,
        "title": "Add auth",
        "state": "open",
        "labels": [{"name": "enhancement"}, {"name": "priority:high"}],
        "milestone": SAMPLE_MILESTONE_RAW,
        "html_url": "https://github.com/owner/repo1/issues/10",
        "created_at": "2026-02-10T12:00:00Z",
        "updated_at": "2026-02-14T15:30:00Z",
        "pull_request": None,
    },
    {
        "number": 11,
        "title": "Fix typo",
        "state": "open",
        "labels": [],
        "milestone": SAMPLE_MILESTONE_RAW,
        "html_url": "https://github.com/owner/repo1/issues/11",
        "created_at": "2026-02-12T09:00:00Z",
        "updated_at": "2026-02-12T09:00:00Z",
    },
]

SAMPLE_ISSUES_WITH_PR = [
    {
        "number": 12,
        "title": "A pull request",
        "state": "open",
        "labels": [],
        "milestone": SAMPLE_MILESTONE_RAW,
        "html_url": "https://github.com/owner/repo1/pull/12",
        "created_at": "2026-02-13T10:00:00Z",
        "updated_at": "2026-02-13T10:00:00Z",
        "pull_request": {"url": "https://api.github.com/repos/owner/repo1/pulls/12"},
    },
    SAMPLE_ISSUES[0],
]

SAMPLE_BACKLOG_ISSUES = [
    {
        "number": 20,
        "title": "Refactor utils",
        "state": "open",
        "labels": [{"name": "tech-debt"}],
        "milestone": None,
        "html_url": "https://github.com/owner/repo1/issues/20",
        "created_at": "2026-01-05T08:00:00Z",
        "updated_at": "2026-02-01T10:00:00Z",
    },
]


class TestRequest:
    async def test_basic_request(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(f"{API_BASE}/test", payload={"ok": True})
            result = await repo._request("GET", "/test")
        assert result == [{"ok": True}]

    async def test_pagination_follows_link_header(self):
        repo = make_repo()
        page1_url = f"{API_BASE}/repos/owner/repo1/issues?state=open"
        page2_url = f"{API_BASE}/repos/owner/repo1/issues?state=open&page=2"

        with aioresponses() as m:
            m.get(
                page1_url,
                payload=[{"number": 1}],
                headers={"Link": f'<{page2_url}>; rel="next"'},
            )
            m.get(
                page2_url,
                payload=[{"number": 2}],
            )
            result = await repo._request("GET", "/repos/owner/repo1/issues", params={"state": "open"})

        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    async def test_no_pagination_when_no_link_header(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(f"{API_BASE}/test", payload=[{"id": 1}])
            result = await repo._request("GET", "/test")

        assert result == [{"id": 1}]


class TestFetchMilestones:
    async def test_returns_milestone_list(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/milestones?state=open&sort=due_on",
                payload=SAMPLE_MILESTONES,
            )
            milestones = await repo.fetch_milestones("owner/repo1")

        assert len(milestones) == 2
        assert milestones[0] == GitHubMilestone(
            number=1,
            title="v1.0",
            due_date=date(2026, 3, 1),
            open_issues=3,
            closed_issues=7,
            state="open",
        )

    async def test_milestone_with_no_due_date(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/milestones?state=open&sort=due_on",
                payload=SAMPLE_MILESTONES,
            )
            milestones = await repo.fetch_milestones("owner/repo1")

        assert milestones[1].due_date is None
        assert milestones[1].title == "v2.0"

    async def test_empty_milestones(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/milestones?state=open&sort=due_on",
                payload=[],
            )
            milestones = await repo.fetch_milestones("owner/repo1")

        assert milestones == []


class TestFetchIssuesByMilestone:
    async def test_returns_issues_for_milestone(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/issues?milestone=1&state=open",
                payload=SAMPLE_ISSUES,
            )
            issues = await repo.fetch_issues_by_milestone("owner/repo1", 1)

        assert len(issues) == 2
        assert issues[0].number == 10
        assert issues[0].title == "Add auth"
        assert issues[0].repo == "owner/repo1"
        assert issues[0].labels == ("enhancement", "priority:high")
        assert issues[0].milestone is not None
        assert issues[0].milestone.title == "v1.0"

    async def test_filters_out_pull_requests(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/issues?milestone=1&state=open",
                payload=SAMPLE_ISSUES_WITH_PR,
            )
            issues = await repo.fetch_issues_by_milestone("owner/repo1", 1)

        # PR (number 12) should be excluded
        assert len(issues) == 1
        assert issues[0].number == 10


class TestFetchIssuesWithoutMilestone:
    async def test_returns_backlog_issues(self):
        repo = make_repo()
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/repos/owner/repo1/issues?assignee=%2A&milestone=none&state=open",
                payload=SAMPLE_BACKLOG_ISSUES,
            )
            issues = await repo.fetch_issues_without_milestone("owner/repo1")

        assert len(issues) == 1
        assert issues[0].number == 20
        assert issues[0].milestone is None
        assert issues[0].labels == ("tech-debt",)
