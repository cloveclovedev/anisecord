import asyncio
import time

import pytest
from aioresponses import CallbackResult, aioresponses

from bot.services.ticktick.auth import TickTickAuth, TickTickAuthError

TICKTICK_TOKEN_URL = "https://ticktick.com/oauth/token"


class TestGetValidToken:
    async def test_returns_current_token_when_not_expired(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="valid_token",
            refresh_token="rtoken",
            expires_at=time.time() + 3600,
        )
        token = await auth.get_valid_token()
        assert token == "valid_token"

    async def test_returns_current_token_when_expires_at_is_zero(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="token_no_expiry",
            refresh_token="rtoken",
            expires_at=0.0,
        )
        token = await auth.get_valid_token()
        assert token == "token_no_expiry"

    async def test_refreshes_when_near_expiry(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old_token",
            refresh_token="rtoken",
            expires_at=time.time() + 30,  # Within 60s buffer
        )
        with aioresponses() as m:
            m.post(
                TICKTICK_TOKEN_URL,
                payload={
                    "access_token": "new_token",
                    "refresh_token": "new_rtoken",
                    "expires_in": 3600,
                },
            )
            token = await auth.get_valid_token()
        assert token == "new_token"
        assert auth.refresh_token == "new_rtoken"


class TestRefresh:
    async def test_successful_refresh(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="old_refresh",
        )
        with aioresponses() as m:
            m.post(
                TICKTICK_TOKEN_URL,
                payload={
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",
                    "expires_in": 7200,
                },
            )
            await auth.refresh()

        assert auth.access_token == "new_access"
        assert auth.refresh_token == "new_refresh"
        assert auth.expires_at > time.time()

    async def test_refresh_without_new_refresh_token(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="keep_this",
        )
        with aioresponses() as m:
            m.post(
                TICKTICK_TOKEN_URL,
                payload={"access_token": "new_access", "expires_in": 3600},
            )
            await auth.refresh()

        assert auth.access_token == "new_access"
        assert auth.refresh_token == "keep_this"

    async def test_refresh_failure_raises_auth_error(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="bad_refresh",
        )
        with aioresponses() as m:
            m.post(TICKTICK_TOKEN_URL, status=400, payload={"error": "invalid_grant"})
            with pytest.raises(TickTickAuthError, match="400"):
                await auth.refresh()

    async def test_concurrent_refresh_only_calls_api_once(self):
        auth = TickTickAuth(
            client_id="cid",
            client_secret="csecret",
            access_token="old",
            refresh_token="rtoken",
            expires_at=0.0,
        )
        call_count = 0

        with aioresponses() as m:

            def callback(url, **kwargs):
                nonlocal call_count
                call_count += 1
                return CallbackResult(
                    payload={
                        "access_token": "refreshed",
                        "refresh_token": "new_r",
                        "expires_in": 3600,
                    }
                )

            m.post(TICKTICK_TOKEN_URL, callback=callback, repeat=True)

            await asyncio.gather(auth.refresh(), auth.refresh(), auth.refresh())

        # Due to double-check pattern, only 1 actual API call should be made
        assert call_count == 1
        assert auth.access_token == "refreshed"
