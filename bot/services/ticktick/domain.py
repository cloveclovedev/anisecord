from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional


class TaskPriority(IntEnum):
    """TickTick API priority values."""
    NONE = 0
    LOW = 1
    MEDIUM = 3
    HIGH = 5


class TaskStatus(IntEnum):
    """TickTick API task status values."""
    ACTIVE = 0
    COMPLETED = 2


class SubTaskStatus(IntEnum):
    """TickTick API subtask (checklist item) status values."""
    ACTIVE = 0
    COMPLETED = 1


@dataclass(frozen=True)
class TickTickSubTask:
    title: str
    status: SubTaskStatus
    sort_order: int


@dataclass(frozen=True)
class TickTickTask:
    id: str
    title: str
    project_id: str
    project_name: str
    status: TaskStatus
    priority: TaskPriority
    is_overdue: bool
    content: str = ""
    tags: tuple[str, ...] = ()
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    is_all_day: bool = False
    sub_tasks: tuple[TickTickSubTask, ...] = ()
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None


@dataclass(frozen=True)
class TickTickProject:
    id: str
    name: str
    color: Optional[str] = None
