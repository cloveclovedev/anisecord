from datetime import datetime
from zoneinfo import ZoneInfo

from bot.services.google_calendar.domain import GoogleCalendarEvent, GoogleCalendarInfo

JST = ZoneInfo("Asia/Tokyo")


class TestGoogleCalendarInfo:
    def test_creation(self):
        cal = GoogleCalendarInfo(id="cal1", summary="Work")
        assert cal.id == "cal1"
        assert cal.summary == "Work"

    def test_frozen(self):
        cal = GoogleCalendarInfo(id="cal1", summary="Work")
        try:
            cal.summary = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestGoogleCalendarEvent:
    def test_creation(self):
        cal = GoogleCalendarInfo(id="cal1", summary="Work")
        event = GoogleCalendarEvent(
            id="ev1",
            summary="Meeting",
            calendar=cal,
            start=datetime(2026, 2, 23, 10, 0, tzinfo=JST),
            end=datetime(2026, 2, 23, 11, 0, tzinfo=JST),
            is_all_day=False,
            location="Office",
            status="confirmed",
        )
        assert event.summary == "Meeting"
        assert event.calendar.summary == "Work"
        assert event.location == "Office"

    def test_all_day_event(self):
        cal = GoogleCalendarInfo(id="cal1", summary="Holidays")
        event = GoogleCalendarEvent(
            id="ev2",
            summary="National Holiday",
            calendar=cal,
            start=datetime(2026, 2, 23, tzinfo=JST),
            end=datetime(2026, 2, 24, tzinfo=JST),
            is_all_day=True,
            location=None,
            status="confirmed",
        )
        assert event.is_all_day is True
        assert event.location is None

    def test_frozen(self):
        cal = GoogleCalendarInfo(id="cal1", summary="Work")
        event = GoogleCalendarEvent(
            id="ev1",
            summary="Meeting",
            calendar=cal,
            start=datetime(2026, 2, 23, 10, 0, tzinfo=JST),
            end=datetime(2026, 2, 23, 11, 0, tzinfo=JST),
            is_all_day=False,
            location=None,
            status="confirmed",
        )
        try:
            event.summary = "changed"
            assert False, "Should be frozen"
        except AttributeError:
            pass
