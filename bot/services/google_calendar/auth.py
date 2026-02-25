import asyncio
import logging
import time
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleCalendarAuthError(Exception):
    """Raised when OAuth token operations fail."""


@dataclass
class GoogleCalendarAuth:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: float = 0.0
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def get_valid_token(self) -> str:
        """Return a valid access token. Proactively refreshes 60s before expiry."""
        if self.expires_at and time.time() >= self.expires_at - 60:
            await self.refresh()
        return self.access_token

    async def refresh(self) -> None:
        """Refresh the access token. Safe to call from multiple coroutines."""
        async with self._refresh_lock:
            if self.expires_at and time.time() < self.expires_at - 60:
                return

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "Google token refresh failed: status=%d body=%s",
                            resp.status,
                            body,
                        )
                        raise GoogleCalendarAuthError(
                            f"Token refresh failed ({resp.status}): {body}"
                        )

                    data = await resp.json()
                    self.access_token = data["access_token"]
                    if "refresh_token" in data:
                        self.refresh_token = data["refresh_token"]
                    if "expires_in" in data:
                        self.expires_at = time.time() + data["expires_in"]

                    logger.info("Google Calendar token refreshed successfully")
