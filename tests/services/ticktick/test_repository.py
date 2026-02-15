import time
from datetime import date
from unittest.mock import patch

from aioresponses import aioresponses

from bot.services.ticktick.auth import TickTickAuth
from bot.services.ticktick.domain import (
    SubTaskStatus,
    TaskPriority,
    TaskStatus,
    TickTickProject,
)
from bot.services.ticktick.repository import TickTickRepository

API_BASE = "https://api.ticktick.com/open/v1"


def make_auth() -> TickTickAuth:
    return TickTickAuth(
        client_id="cid",
        client_secret="csecret",
        access_token="test_token",
        refresh_token="rtoken",
        expires_at=time.time() + 3600,
    )


# --- Sample API response fixtures ---

SAMPLE_PROJECTS = [
    {"id": "proj1", "name": "Work", "color": "#4772FA"},
    {"id": "proj2", "name": "Personal", "color": None},
]

SAMPLE_PROJECT_DATA_PROJ1 = {
    "tasks": [
        {
            "id": "task1",
            "title": "Review PR",
            "projectId": "proj1",
            "status": 0,
            "priority": 5,
            "content": "Check the new feature branch",
            "tags": ["dev"],
            "dueDate": "2026-02-15T09:00:00.000+0000",
            "startDate": "2026-02-15T08:00:00.000+0000",
            "isAllDay": False,
            "items": [
                {"title": "Read code", "status": 0, "sortOrder": 0},
                {"title": "Leave comments", "status": 1, "sortOrder": 1},
            ],
            "createdTime": "2026-02-10T00:00:00.000+0000",
            "modifiedTime": "2026-02-14T12:00:00.000+0000",
        },
        {
            "id": "task2",
            "title": "Completed task",
            "projectId": "proj1",
            "status": 2,
            "priority": 0,
            "dueDate": "2026-02-15T09:00:00.000+0000",
        },
    ]
}

SAMPLE_PROJECT_DATA_PROJ2 = {
    "tasks": [
        {
            "id": "task3",
            "title": "Overdue grocery shopping",
            "projectId": "proj2",
            "status": 0,
            "priority": 1,
            "dueDate": "2026-02-13T00:00:00.000+0000",
            "isAllDay": True,
        },
        {
            "id": "task4",
            "title": "Future task",
            "projectId": "proj2",
            "status": 0,
            "priority": 3,
            "dueDate": "2026-02-20T00:00:00.000+0000",
        },
        {
            "id": "task5",
            "title": "No due date task",
            "projectId": "proj2",
            "status": 0,
            "priority": 0,
        },
    ]
}


class TestFetchProjects:
    async def test_returns_project_list(self):
        repo = TickTickRepository(make_auth())
        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            projects = await repo.fetch_projects()

        assert len(projects) == 2
        assert projects[0] == TickTickProject(id="proj1", name="Work", color="#4772FA")
        assert projects[1] == TickTickProject(id="proj2", name="Personal", color=None)


class TestFetchActionableTasks:
    @patch("bot.services.ticktick.repository._today_jst")
    async def test_returns_today_and_overdue_tasks(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            m.get(f"{API_BASE}/project/proj1/data", payload=SAMPLE_PROJECT_DATA_PROJ1)
            m.get(f"{API_BASE}/project/proj2/data", payload=SAMPLE_PROJECT_DATA_PROJ2)

            tasks = await repo.fetch_actionable_tasks()

        # task1: due today, active -> included
        # task2: due today, completed -> excluded
        # task3: overdue (Feb 13), active -> included
        # task4: future (Feb 20) -> excluded
        # task5: no due date -> excluded
        assert len(tasks) == 2
        titles = {t.title for t in tasks}
        assert titles == {"Review PR", "Overdue grocery shopping"}

    @patch("bot.services.ticktick.repository._today_jst")
    async def test_overdue_flag_is_set_correctly(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            m.get(f"{API_BASE}/project/proj1/data", payload=SAMPLE_PROJECT_DATA_PROJ1)
            m.get(f"{API_BASE}/project/proj2/data", payload=SAMPLE_PROJECT_DATA_PROJ2)

            tasks = await repo.fetch_actionable_tasks()

        task_map = {t.title: t for t in tasks}
        assert task_map["Review PR"].is_overdue is False
        assert task_map["Overdue grocery shopping"].is_overdue is True

    @patch("bot.services.ticktick.repository._today_jst")
    async def test_task_fields_are_converted_correctly(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)
            m.get(f"{API_BASE}/project/proj1/data", payload=SAMPLE_PROJECT_DATA_PROJ1)
            m.get(f"{API_BASE}/project/proj2/data", payload=SAMPLE_PROJECT_DATA_PROJ2)

            tasks = await repo.fetch_actionable_tasks()

        task = next(t for t in tasks if t.title == "Review PR")
        assert task.id == "task1"
        assert task.project_id == "proj1"
        assert task.project_name == "Work"
        assert task.status == TaskStatus.ACTIVE
        assert task.priority == TaskPriority.HIGH
        assert task.content == "Check the new feature branch"
        assert task.tags == ("dev",)
        assert task.is_all_day is False
        assert len(task.sub_tasks) == 2
        assert task.sub_tasks[0].title == "Read code"
        assert task.sub_tasks[0].status == SubTaskStatus.ACTIVE
        assert task.sub_tasks[1].status == SubTaskStatus.COMPLETED

    @patch("bot.services.ticktick.repository._today_jst")
    async def test_empty_projects(self, mock_today):
        mock_today.return_value = date(2026, 2, 15)
        repo = TickTickRepository(make_auth())

        with aioresponses() as m:
            m.get(f"{API_BASE}/project", payload=[])
            tasks = await repo.fetch_actionable_tasks()

        assert tasks == []


class TestRequestRetry:
    async def test_retries_on_401(self):
        auth = make_auth()
        repo = TickTickRepository(auth)

        with aioresponses() as m:
            # First call returns 401
            m.get(f"{API_BASE}/project", status=401)
            # After refresh, second call succeeds
            m.post(
                "https://ticktick.com/oauth/token",
                payload={
                    "access_token": "new_token",
                    "expires_in": 3600,
                },
            )
            m.get(f"{API_BASE}/project", payload=SAMPLE_PROJECTS)

            projects = await repo.fetch_projects()

        assert len(projects) == 2
        assert auth.access_token == "new_token"
