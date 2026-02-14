import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .auth import TickTickAuth
from .domain import (
    SubTaskStatus,
    TaskPriority,
    TaskStatus,
    TickTickProject,
    TickTickSubTask,
    TickTickTask,
)

logger = logging.getLogger(__name__)

TICKTICK_API_BASE = "https://api.ticktick.com/open/v1"
JST = ZoneInfo("Asia/Tokyo")


def _today_jst() -> date:
    """Return today's date in JST. Extracted for testability."""
    return datetime.now(JST).date()


class TickTickRepository:
    def __init__(self, auth: TickTickAuth):
        self._auth = auth

    async def fetch_projects(self) -> list[TickTickProject]:
        """Fetch all projects."""
        data = await self._request("GET", "/project")
        return [_to_project(p) for p in data]

    async def fetch_actionable_tasks(self) -> list[TickTickTask]:
        """Fetch active tasks that are due today or overdue, across all projects."""
        projects = await self.fetch_projects()
        project_map = {p.id: p.name for p in projects}

        today = _today_jst()
        result: list[TickTickTask] = []

        for project in projects:
            data = await self._request("GET", f"/project/{project.id}/data")
            for raw_task in data.get("tasks", []):
                task = _to_task(raw_task, project_map, today)
                if task is None:
                    continue
                result.append(task)

        return result

    async def _request(self, method: str, path: str) -> Any:
        """Make an API request. Retries once on 401 after refreshing the token."""
        token = await self._auth.get_valid_token()
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{TICKTICK_API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status == 401:
                    # Invalidate cached expiry so the refresh double-check
                    # doesn't skip the actual token exchange.
                    self._auth.expires_at = 0.0
                    await self._auth.refresh()
                    token = await self._auth.get_valid_token()
                    # Retry once with new token — need a new request
                    async with session.request(
                        method,
                        f"{TICKTICK_API_BASE}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()

                resp.raise_for_status()
                return await resp.json()


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse TickTick datetime string to datetime object."""
    if not value:
        return None
    # TickTick format: "2026-02-15T09:00:00.000+0000"
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        logger.warning("Failed to parse datetime: %s", value)
        return None


def _to_project(data: dict) -> TickTickProject:
    return TickTickProject(
        id=data["id"],
        name=data["name"],
        color=data.get("color"),
    )


def _to_task(
    data: dict, project_map: dict[str, str], today: date
) -> TickTickTask | None:
    """Convert API response to domain object. Returns None if not actionable."""
    status = TaskStatus(data.get("status", 0))
    if status != TaskStatus.ACTIVE:
        return None

    due_date = _parse_datetime(data.get("dueDate"))
    if due_date is None:
        return None

    due_date_local = due_date.astimezone(JST).date()
    if due_date_local > today:
        return None

    is_overdue = due_date_local < today

    sub_tasks = tuple(
        TickTickSubTask(
            title=item.get("title", ""),
            status=SubTaskStatus(item.get("status", 0)),
            sort_order=item.get("sortOrder", 0),
        )
        for item in data.get("items", [])
    )

    tags = tuple(data.get("tags", []))

    return TickTickTask(
        id=data["id"],
        title=data["title"],
        project_id=data.get("projectId", ""),
        project_name=project_map.get(data.get("projectId", ""), ""),
        status=status,
        priority=TaskPriority(data.get("priority", 0)),
        is_overdue=is_overdue,
        content=data.get("content", ""),
        tags=tags,
        due_date=due_date,
        start_date=_parse_datetime(data.get("startDate")),
        is_all_day=data.get("isAllDay", False),
        sub_tasks=sub_tasks,
        created_time=_parse_datetime(data.get("createdTime")),
        modified_time=_parse_datetime(data.get("modifiedTime")),
    )
