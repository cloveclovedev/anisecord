from bot.services.ticktick.domain import (
    TaskPriority,
    TaskStatus,
    SubTaskStatus,
    TickTickSubTask,
    TickTickTask,
    TickTickProject,
)


class TestTaskPriority:
    def test_values_match_ticktick_api(self):
        assert TaskPriority.NONE == 0
        assert TaskPriority.LOW == 1
        assert TaskPriority.MEDIUM == 3
        assert TaskPriority.HIGH == 5


class TestTaskStatus:
    def test_values_match_ticktick_api(self):
        assert TaskStatus.ACTIVE == 0
        assert TaskStatus.COMPLETED == 2


class TestSubTaskStatus:
    def test_values_differ_from_task_status(self):
        assert SubTaskStatus.ACTIVE == 0
        assert SubTaskStatus.COMPLETED == 1


class TestTickTickSubTask:
    def test_creation(self):
        sub = TickTickSubTask(
            title="Buy milk", status=SubTaskStatus.ACTIVE, sort_order=0
        )
        assert sub.title == "Buy milk"
        assert sub.status == SubTaskStatus.ACTIVE
        assert sub.sort_order == 0

    def test_frozen(self):
        sub = TickTickSubTask(
            title="Buy milk", status=SubTaskStatus.ACTIVE, sort_order=0
        )
        try:
            sub.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestTickTickTask:
    def test_creation_minimal(self):
        task = TickTickTask(
            id="task1",
            title="Test task",
            project_id="proj1",
            project_name="Work",
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.HIGH,
            is_overdue=False,
        )
        assert task.id == "task1"
        assert task.title == "Test task"
        assert task.project_name == "Work"
        assert task.priority == TaskPriority.HIGH
        assert task.is_overdue is False
        assert task.content == ""
        assert task.tags == ()
        assert task.due_date is None
        assert task.sub_tasks == ()

    def test_creation_with_all_fields(self):
        from datetime import datetime

        sub = TickTickSubTask(
            title="Step 1", status=SubTaskStatus.COMPLETED, sort_order=0
        )
        task = TickTickTask(
            id="task2",
            title="Full task",
            project_id="proj2",
            project_name="Personal",
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.MEDIUM,
            is_overdue=True,
            content="Some notes",
            tags=("urgent", "home"),
            due_date=datetime(2026, 2, 14, 9, 0),
            start_date=datetime(2026, 2, 14, 8, 0),
            is_all_day=True,
            sub_tasks=(sub,),
            created_time=datetime(2026, 2, 10),
            modified_time=datetime(2026, 2, 14),
        )
        assert task.is_overdue is True
        assert task.tags == ("urgent", "home")
        assert len(task.sub_tasks) == 1
        assert task.sub_tasks[0].title == "Step 1"

    def test_frozen(self):
        task = TickTickTask(
            id="t",
            title="t",
            project_id="p",
            project_name="P",
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.NONE,
            is_overdue=False,
        )
        try:
            task.title = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestTickTickProject:
    def test_creation(self):
        proj = TickTickProject(id="p1", name="Work")
        assert proj.id == "p1"
        assert proj.name == "Work"
        assert proj.color is None

    def test_with_color(self):
        proj = TickTickProject(id="p2", name="Personal", color="#FF0000")
        assert proj.color == "#FF0000"
