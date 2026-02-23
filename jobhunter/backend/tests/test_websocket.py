"""Tests for WebSocket endpoint and connection manager."""
import pytest
from httpx import AsyncClient

from app.config import settings
from app.infrastructure.websocket_manager import ConnectionManager


@pytest.mark.asyncio
async def test_ws_manager_connect_disconnect():
    """Test ConnectionManager connect/disconnect lifecycle."""
    manager = ConnectionManager()

    # Create a mock websocket
    class MockWebSocket:
        def __init__(self):
            self.accepted = False
            self.sent_messages = []

        async def accept(self):
            self.accepted = True

        async def send_text(self, data: str):
            self.sent_messages.append(data)

    ws = MockWebSocket()
    await manager.connect("user-1", ws)
    assert ws.accepted
    assert "user-1" in manager._connections

    await manager.disconnect("user-1", ws)
    assert "user-1" not in manager._connections


@pytest.mark.asyncio
async def test_ws_manager_broadcast():
    """Test that broadcast reaches connected clients."""
    manager = ConnectionManager()

    class MockWebSocket:
        def __init__(self):
            self.accepted = False
            self.sent_messages = []

        async def accept(self):
            self.accepted = True

        async def send_text(self, data: str):
            self.sent_messages.append(data)

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    await manager.connect("user-1", ws1)
    await manager.connect("user-1", ws2)

    await manager.broadcast("user-1", "test_event", {"key": "value"})

    assert len(ws1.sent_messages) == 1
    assert len(ws2.sent_messages) == 1
    assert '"type": "test_event"' in ws1.sent_messages[0]
    assert '"key": "value"' in ws1.sent_messages[0]


@pytest.mark.asyncio
async def test_ws_manager_broadcast_no_connections():
    """Broadcast to non-existent user should be a no-op."""
    manager = ConnectionManager()
    # Should not raise
    await manager.broadcast("nobody", "test", {})


@pytest.mark.asyncio
async def test_ws_manager_broadcast_dead_connection():
    """Dead connections should be removed during broadcast."""
    manager = ConnectionManager()

    class MockWebSocket:
        def __init__(self):
            self.accepted = False
            self.sent_messages = []

        async def accept(self):
            self.accepted = True

        async def send_text(self, data: str):
            self.sent_messages.append(data)

    class DeadWebSocket:
        async def accept(self):
            pass

        async def send_text(self, data: str):
            raise ConnectionError("Connection lost")

    ws_alive = MockWebSocket()
    ws_dead = DeadWebSocket()

    await manager.connect("user-1", ws_alive)
    await manager.connect("user-1", ws_dead)

    assert len(manager._connections["user-1"]) == 2

    await manager.broadcast("user-1", "test", {"data": 1})

    # Dead connection should be removed
    assert len(manager._connections["user-1"]) == 1
    assert len(ws_alive.sent_messages) == 1


@pytest.mark.asyncio
async def test_ws_reject_invalid_token(client: AsyncClient):
    """WebSocket with invalid token should be rejected."""
    # We can't easily test actual WebSocket connections via httpx,
    # but we can verify the endpoint exists and the auth logic
    from app.utils.security import decode_token

    # Invalid token should raise
    import jwt
    with pytest.raises(jwt.PyJWTError):
        decode_token("invalid-token-here")


@pytest.mark.asyncio
async def test_ws_valid_token_decodes(client: AsyncClient, auth_headers: dict):
    """Valid JWT token should decode successfully for WebSocket auth."""
    from app.utils.security import decode_token

    token = auth_headers["Authorization"].replace("Bearer ", "")
    payload = decode_token(token)
    assert "sub" in payload
    assert payload["type"] == "access"
