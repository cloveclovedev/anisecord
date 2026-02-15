import logging
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .domain import GitHubIssue, GitHubMilestone

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
JST = ZoneInfo("Asia/Tokyo")

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def _parse_due_date(value: str | None) -> date | None:
    """Parse GitHub milestone due_on to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").date()
    except ValueError:
        logger.warning("Failed to parse due_on: %s", value)
        return None


def _to_milestone(data: dict) -> GitHubMilestone:
    return GitHubMilestone(
        number=data["number"],
        title=data["title"],
        due_date=_parse_due_date(data.get("due_on")),
        open_issues=data.get("open_issues", 0),
        closed_issues=data.get("closed_issues", 0),
        state=data.get("state", "open"),
    )


class GitHubRepository:
    def __init__(self, token: str, repos: list[str]):
        self._token = token
        self._repos = repos

    async def _request(
        self, method: str, path: str, params: dict | None = None
    ) -> list[Any]:
        """Make a GitHub API request. Returns aggregated results across all pages."""
        url = f"{GITHUB_API_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
        }
        timeout = aiohttp.ClientTimeout(total=30)
        all_items: list[Any] = []

        async with aiohttp.ClientSession(timeout=timeout) as session:
            current_url: str | None = url
            current_params = params

            while current_url:
                async with session.request(
                    method,
                    current_url,
                    headers=headers,
                    params=current_params,
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    if isinstance(data, list):
                        all_items.extend(data)
                    else:
                        all_items.append(data)

                    # Check for next page
                    link = resp.headers.get("Link", "")
                    match = _LINK_NEXT_RE.search(link)
                    if match:
                        current_url = match.group(1)
                        current_params = None  # params are in the URL
                    else:
                        current_url = None

        return all_items

    async def fetch_milestones(self, repo: str) -> list[GitHubMilestone]:
        """Fetch open milestones for a repo."""
        data = await self._request(
            "GET", f"/repos/{repo}/milestones", params={"state": "open", "sort": "due_on"}
        )
        return [_to_milestone(m) for m in data]
