from aioresponses import aioresponses

from bot.services.github.repository import GitHubRepository

API_BASE = "https://api.github.com"


def make_repo(repos: list[str] | None = None) -> GitHubRepository:
    return GitHubRepository(
        token="test_token",
        repos=repos or ["owner/repo1"],
    )


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
