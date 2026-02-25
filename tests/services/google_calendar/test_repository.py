import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from aioresponses import aioresponses

from bot.services.google_calendar.auth import GoogleCalendarAuth
from bot.services.google_calendar.repository import GoogleCalendarRepository

API_BASE = "https://www.googleapis.com/calendar/v3"
JST = ZoneInfo("Asia/Tokyo")


def make_auth() -> GoogleCalendarAuth:
    return GoogleCalendarAuth(
        client_id="cid",
        client_secret="csecret",
        access_token="test_token",
        refresh_token="rtoken",
        expires_at=time.time() + 3600,
    )


SAMPLE_CALENDAR_LIST = {
    "kind": "calendar#calendarList",
    "items": [
        {"id": "cal_work", "summary": "Work"},
        {"id": "cal_personal", "summary": "mkuri"},
    ],
}

SAMPLE_EVENTS_WORK = {
    "kind": "calendar#events",
    "items": [
        {
            "id": "ev1",
            "summary": "WRK | @品川",
            "status": "confirmed",
            "start": {"dateTime": "2026-02-23T10:30:00+09:00"},
            "end": {"dateTime": "2026-02-23T20:00:00+09:00"},
            "location": "品川オフィス",
        },
    ],
}

SAMPLE_EVENTS_PERSONAL = {
    "kind": "calendar#events",
    "items": [
        {
            "id": "ev2",
            "summary": "Emperor's Birthday",
            "status": "confirmed",
            "start": {"date": "2026-02-23"},
            "end": {"date": "2026-02-24"},
        },
    ],
}


class TestFetchCalendars:
    async def test_returns_calendar_list(self):
        repo = GoogleCalendarRepository(make_auth())
        with aioresponses() as m:
            m.get(
                f"{API_BASE}/users/me/calendarList",
                payload=SAMPLE_CALENDAR_LIST,
            )
            calendars = await repo.fetch_calendars()

        assert len(calendars) == 2
        assert calendars[0].id == "cal_work"
        assert calendars[0].summary == "Work"
        assert calendars[1].summary == "mkuri"


class TestFetchEvents:
    async def test_returns_events_from_all_calendars(self):
        repo = GoogleCalendarRepository(make_auth())
        time_min = datetime(2026, 2, 23, 0, 0, tzinfo=JST)
        time_max = datetime(2026, 3, 1, 0, 0, tzinfo=JST)

        with aioresponses() as m:
            m.get(
                f"{API_BASE}/users/me/calendarList",
                payload=SAMPLE_CALENDAR_LIST,
            )
            m.get(
                re.compile(rf"{API_BASE}/calendars/cal_work/events.*"),
                payload=SAMPLE_EVENTS_WORK,
            )
            m.get(
                re.compile(rf"{API_BASE}/calendars/cal_personal/events.*"),
                payload=SAMPLE_EVENTS_PERSONAL,
            )
            events = await repo.fetch_events(time_min=time_min, time_max=time_max)

        assert len(events) == 2

        timed_event = next(e for e in events if e.summary == "WRK | @品川")
        assert timed_event.calendar.summary == "Work"
        assert timed_event.is_all_day is False
        assert timed_event.location == "品川オフィス"
        assert timed_event.start.hour == 10
        assert timed_event.start.minute == 30

        all_day_event = next(e for e in events if e.summary == "Emperor's Birthday")
        assert all_day_event.is_all_day is True
        assert all_day_event.calendar.summary == "mkuri"

    async def test_handles_pagination(self):
        repo = GoogleCalendarRepository(make_auth())
        time_min = datetime(2026, 2, 23, 0, 0, tzinfo=JST)
        time_max = datetime(2026, 3, 1, 0, 0, tzinfo=JST)

        page1 = {
            "kind": "calendar#events",
            "nextPageToken": "page2token",
            "items": [
                {
                    "id": "ev1",
                    "summary": "Event 1",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-02-23T10:00:00+09:00"},
                    "end": {"dateTime": "2026-02-23T11:00:00+09:00"},
                },
            ],
        }
        page2 = {
            "kind": "calendar#events",
            "items": [
                {
                    "id": "ev2",
                    "summary": "Event 2",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-02-23T14:00:00+09:00"},
                    "end": {"dateTime": "2026-02-23T15:00:00+09:00"},
                },
            ],
        }

        cal_list = {
            "kind": "calendar#calendarList",
            "items": [{"id": "cal1", "summary": "Test"}],
        }

        with aioresponses() as m:
            m.get(f"{API_BASE}/users/me/calendarList", payload=cal_list)
            m.get(re.compile(rf"{API_BASE}/calendars/cal1/events.*"), payload=page1)
            m.get(re.compile(rf"{API_BASE}/calendars/cal1/events.*"), payload=page2)
            events = await repo.fetch_events(time_min=time_min, time_max=time_max)

        assert len(events) == 2

    async def test_skips_cancelled_events(self):
        repo = GoogleCalendarRepository(make_auth())
        time_min = datetime(2026, 2, 23, 0, 0, tzinfo=JST)
        time_max = datetime(2026, 3, 1, 0, 0, tzinfo=JST)

        events_payload = {
            "kind": "calendar#events",
            "items": [
                {
                    "id": "ev1",
                    "summary": "Active Event",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-02-23T10:00:00+09:00"},
                    "end": {"dateTime": "2026-02-23T11:00:00+09:00"},
                },
                {
                    "id": "ev2",
                    "summary": "Cancelled Event",
                    "status": "cancelled",
                    "start": {"dateTime": "2026-02-23T12:00:00+09:00"},
                    "end": {"dateTime": "2026-02-23T13:00:00+09:00"},
                },
            ],
        }
        cal_list = {
            "kind": "calendar#calendarList",
            "items": [{"id": "cal1", "summary": "Test"}],
        }

        with aioresponses() as m:
            m.get(f"{API_BASE}/users/me/calendarList", payload=cal_list)
            m.get(
                re.compile(rf"{API_BASE}/calendars/cal1/events.*"),
                payload=events_payload,
            )
            events = await repo.fetch_events(time_min=time_min, time_max=time_max)

        assert len(events) == 1
        assert events[0].summary == "Active Event"

    async def test_retries_on_401(self):
        auth = make_auth()
        repo = GoogleCalendarRepository(auth)

        cal_list = {
            "kind": "calendar#calendarList",
            "items": [{"id": "cal1", "summary": "Test"}],
        }

        with aioresponses() as m:
            # First call returns 401
            m.get(f"{API_BASE}/users/me/calendarList", status=401)
            # Token refresh
            m.post(
                "https://oauth2.googleapis.com/token",
                payload={"access_token": "new_token", "expires_in": 3600},
            )
            # Retry succeeds
            m.get(f"{API_BASE}/users/me/calendarList", payload=cal_list)

            calendars = await repo.fetch_calendars()

        assert len(calendars) == 1
        assert auth.access_token == "new_token"
