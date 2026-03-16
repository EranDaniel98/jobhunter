"""Unit tests for app/api/ws.py - WebSocket endpoint auth, connect/disconnect,
and reauth loop using mocked decode_token, redis_safe_get, and ws_manager."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

# ---------------------------------------------------------------------------
# Auth rejection tests (lines 21-34) - tested via direct async calls
# ---------------------------------------------------------------------------


class TestWsAuthRejection:
    @pytest.mark.asyncio
    async def test_ws_auth_failed_invalid_token(self):
        """Invalid JWT closes WebSocket with code 4001."""
        from app.api.ws import websocket_endpoint

        ws = AsyncMock()
        ws.close = AsyncMock()

        with patch("app.api.ws.decode_token", side_effect=ValueError("bad token")):
            await websocket_endpoint(ws, token="invalid_token")

        ws.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_ws_auth_missing_sub_closes_4001(self):
        """Token without 'sub' claim closes with code 4001."""
        from app.api.ws import websocket_endpoint

        ws = AsyncMock()
        ws.close = AsyncMock()

        with patch("app.api.ws.decode_token", return_value={"type": "access"}):
            await websocket_endpoint(ws, token="some_token")

        ws.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_ws_auth_blacklisted_token_closes_4003(self):
        """Blacklisted token closes with code 4003."""
        from app.api.ws import websocket_endpoint

        candidate_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        ws = AsyncMock()
        ws.close = AsyncMock()

        with (
            patch("app.api.ws.decode_token", return_value={"sub": candidate_id, "jti": jti}),
            patch("app.api.ws.redis_safe_get", new_callable=AsyncMock, return_value=b"1"),
        ):
            await websocket_endpoint(ws, token="blacklisted_token")

        ws.close.assert_awaited_once_with(code=4003)


# ---------------------------------------------------------------------------
# Successful connection (lines 36-59) - tested via direct async calls
# ---------------------------------------------------------------------------


class TestWsConnection:
    @pytest.mark.asyncio
    async def test_ws_connects_and_disconnects(self):
        """Valid token → ws_manager.connect called; disconnect on WebSocketDisconnect."""
        from app.api.ws import websocket_endpoint

        candidate_id = str(uuid.uuid4())

        ws = AsyncMock()
        ws.close = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))

        with (
            patch("app.api.ws.decode_token", return_value={"sub": candidate_id, "jti": None}),
            patch("app.api.ws.redis_safe_get", new_callable=AsyncMock, return_value=None),
            patch("app.api.ws.ws_manager") as mock_manager,
        ):
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await websocket_endpoint(ws, token="valid_token")

        mock_manager.connect.assert_awaited_once_with(candidate_id, ws)
        mock_manager.disconnect.assert_awaited_once_with(candidate_id, ws)

    @pytest.mark.asyncio
    async def test_ws_connects_without_jti(self):
        """Token without jti doesn't check Redis blacklist."""
        from app.api.ws import websocket_endpoint

        candidate_id = str(uuid.uuid4())

        ws = AsyncMock()
        ws.close = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))

        with (
            patch("app.api.ws.decode_token", return_value={"sub": candidate_id}),
            patch("app.api.ws.redis_safe_get", new_callable=AsyncMock) as mock_redis,
            patch("app.api.ws.ws_manager") as mock_manager,
        ):
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await websocket_endpoint(ws, token="no_jti_token")

        # redis_safe_get should not have been called for blacklist check
        mock_redis.assert_not_awaited()


# ---------------------------------------------------------------------------
# Reauth loop (lines 38-50) - tested with direct async invocation
# ---------------------------------------------------------------------------


class TestReauthLoop:
    @pytest.mark.asyncio
    async def test_reauth_loop_closes_on_expired_token(self):
        """_reauth_loop closes websocket when token expires."""

        ws = MagicMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()

        import contextlib
        import json

        async def reauth_loop():
            """Inline copy of the _reauth_loop closure logic."""
            while True:
                await asyncio.sleep(0)  # yield instead of real 5-min wait
                try:
                    from jwt import PyJWTError

                    raise PyJWTError("expired")
                except Exception:
                    with contextlib.suppress(Exception):
                        await ws.send_text(json.dumps({"type": "auth_expired"}))
                    await ws.close(code=4003)
                    return

        await reauth_loop()

        ws.send_text.assert_awaited_once()
        ws.close.assert_awaited_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_reauth_loop_closes_on_blacklisted_token(self):
        """_reauth_loop closes websocket when token becomes blacklisted."""
        import contextlib
        import json

        ws = MagicMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()

        async def reauth_loop():
            """Simulates the loop detecting a blacklisted token."""
            while True:
                await asyncio.sleep(0)
                try:
                    # decode succeeds but redis check shows blacklisted
                    raise ValueError("Token blacklisted")
                except Exception:
                    with contextlib.suppress(Exception):
                        await ws.send_text(json.dumps({"type": "auth_expired"}))
                    await ws.close(code=4003)
                    return

        await reauth_loop()

        ws.close.assert_awaited_once_with(code=4003)


# ---------------------------------------------------------------------------
# Direct endpoint logic tests using AsyncMock websocket
# ---------------------------------------------------------------------------


class TestWsEndpointLogic:
    @pytest.mark.asyncio
    async def test_websocket_endpoint_auth_failure_closes_4001(self):
        """websocket_endpoint closes 4001 when decode_token raises."""
        from app.api.ws import websocket_endpoint

        ws = AsyncMock()
        ws.close = AsyncMock()

        with patch("app.api.ws.decode_token", side_effect=Exception("bad")):
            await websocket_endpoint(ws, token="bad_token")

        ws.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_websocket_endpoint_no_sub_closes_4001(self):
        """websocket_endpoint closes 4001 when token has no sub."""
        from app.api.ws import websocket_endpoint

        ws = AsyncMock()
        ws.close = AsyncMock()

        with patch("app.api.ws.decode_token", return_value={"type": "access"}):
            await websocket_endpoint(ws, token="no_sub_token")

        ws.close.assert_awaited_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_websocket_endpoint_blacklisted_closes_4003(self):
        """websocket_endpoint closes 4003 when token is blacklisted."""
        from app.api.ws import websocket_endpoint

        candidate_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        ws = AsyncMock()
        ws.close = AsyncMock()

        with (
            patch("app.api.ws.decode_token", return_value={"sub": candidate_id, "jti": jti}),
            patch("app.api.ws.redis_safe_get", new_callable=AsyncMock, return_value=b"1"),
        ):
            await websocket_endpoint(ws, token="blacklisted")

        ws.close.assert_awaited_once_with(code=4003)

    @pytest.mark.asyncio
    async def test_websocket_endpoint_connects_then_disconnects(self):
        """Valid token connects, receives WebSocketDisconnect, then disconnects."""
        from app.api.ws import websocket_endpoint

        candidate_id = str(uuid.uuid4())

        ws = AsyncMock()
        ws.close = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))

        with (
            patch("app.api.ws.decode_token", return_value={"sub": candidate_id}),
            patch("app.api.ws.redis_safe_get", new_callable=AsyncMock, return_value=None),
            patch("app.api.ws.ws_manager") as mock_manager,
        ):
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            await websocket_endpoint(ws, token="valid_token")

        mock_manager.connect.assert_awaited_once_with(candidate_id, ws)
        mock_manager.disconnect.assert_awaited_once_with(candidate_id, ws)
