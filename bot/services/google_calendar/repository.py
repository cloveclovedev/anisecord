import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import aiohttp

from .auth import GoogleCalendarAuth
from .domain import GoogleCalendarEvent, GoogleCalendarInfo

logger = logging.getLogger(__name__)

GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarRepository:
    def __init__(self, auth: GoogleCalendarAuth):
        self._auth = auth

    async def fetch_calendars(self) -> list[GoogleCalendarInfo]:
        """Fetch all calendars the user has access to."""
        data = await self._request("GET", "/users/me/calendarList")
        return [
            GoogleCalendarInfo(id=item["id"], summary=item["summary"])
            for item in data.get("items", [])
        ]

    async def fetch_events(
        self,
        time_min: datetime,
        time_max: datetime,
    ) -> list[GoogleCalendarEvent]:
        """Fetch events from all calendars within the time range."""
        calendars = await self.fetch_calendars()
        all_events: list[GoogleCalendarEvent] = []

        for cal in calendars:
            events = await self._fetch_calendar_events(cal, time_min, time_max)
            all_events.extend(events)

        return all_events

    async def _fetch_calendar_events(
        self,
        calendar: GoogleCalendarInfo,
        time_min: datetime,
        time_max: datetime,
    ) -> list[GoogleCalendarEvent]:
        """Fetch events from a single calendar, handling pagination."""
        events: list[GoogleCalendarEvent] = []
        params: dict[str, str] = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        }

        while True:
            data = await self._request(
                "GET",
                f"/calendars/{quote(calendar.id, safe='')}/events",
                params=params,
            )

            for item in data.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                events.append(_to_event(item, calendar))

            next_page = data.get("nextPageToken")
            if not next_page:
                break
            params["pageToken"] = next_page

        return events

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Make an API request. Retries once on 401 after refreshing the token."""
        token = await self._auth.get_valid_token()
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{GOOGLE_CALENDAR_API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            ) as resp:
                if resp.status == 401:
                    self._auth.expires_at = 0.0
                    await self._auth.refresh()
                    token = await self._auth.get_valid_token()
                    async with session.request(
                        method,
                        f"{GOOGLE_CALENDAR_API_BASE}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        params=params,
                    ) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()

                resp.raise_for_status()
                return await resp.json()


def _parse_event_time(time_obj: dict) -> tuple[datetime, bool]:
    """Parse event start/end. Returns (datetime, is_all_day)."""
    if "dateTime" in time_obj:
        return datetime.fromisoformat(time_obj["dateTime"]), False
    # All-day event: "date" field is YYYY-MM-DD
    date_str = time_obj["date"]
    return datetime.fromisoformat(date_str), True


def _to_event(data: dict, calendar: GoogleCalendarInfo) -> GoogleCalendarEvent:
    """Convert API response to domain object."""
    start, start_all_day = _parse_event_time(data["start"])
    end, _ = _parse_event_time(data["end"])

    return GoogleCalendarEvent(
        id=data["id"],
        summary=data.get("summary", "(no title)"),
        calendar=calendar,
        start=start,
        end=end,
        is_all_day=start_all_day,
        location=data.get("location"),
        status=data.get("status", "confirmed"),
    )
