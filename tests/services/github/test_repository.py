from datetime import date

from aioresponses import aioresponses

from bot.services.github.domain import GitHubMilestone
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
