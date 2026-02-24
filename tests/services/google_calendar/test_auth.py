import time

from aioresponses import aioresponses

from bot.services.google_calendar.auth import GoogleCalendarAuth, GoogleCalendarAuthError

TOKEN_URL = "https://oauth2.googleapis.com/token"


def make_auth() -> GoogleCalendarAuth:
    return GoogleCalendarAuth(
        client_id="cid",
        client_secret="csecret",
        access_token="test_token",
        refresh_token="rtoken",
        expires_at=time.time() + 3600,
    )


class TestGetValidToken:
    async def test_returns_current_token_when_valid(self):
        auth = make_auth()
        token = await auth.get_valid_token()
        assert token == "test_token"

    async def test_refreshes_when_near_expiry(self):
        auth = make_auth()
        auth.expires_at = time.time() + 30  # within 60s buffer

        with aioresponses() as m:
            m.post(
                TOKEN_URL,
                payload={
                    "access_token": "new_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
            token = await auth.get_valid_token()

        assert token == "new_token"


class TestRefresh:
    async def test_updates_tokens_on_success(self):
        auth = make_auth()
        auth.expires_at = 0.0

        with aioresponses() as m:
            m.post(
                TOKEN_URL,
                payload={
                    "access_token": "refreshed",
                    "expires_in": 7200,
                    "token_type": "Bearer",
                },
            )
            await auth.refresh()

        assert auth.access_token == "refreshed"
        assert auth.expires_at > time.time()

    async def test_raises_on_failure(self):
        auth = make_auth()
        auth.expires_at = 0.0

        with aioresponses() as m:
            m.post(TOKEN_URL, status=400, body="invalid_grant")
            try:
                await auth.refresh()
                assert False, "Should have raised"
            except GoogleCalendarAuthError:
                pass
