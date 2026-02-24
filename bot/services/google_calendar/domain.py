from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GoogleCalendarInfo:
    id: str
    summary: str


@dataclass(frozen=True)
class GoogleCalendarEvent:
    id: str
    summary: str
    calendar: GoogleCalendarInfo
    start: datetime
    end: datetime
    is_all_day: bool
    location: str | None
    status: str
