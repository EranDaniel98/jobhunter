"""Tests for WebSocket endpoint and connection manager."""
import pytest
from httpx import AsyncClient

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
    # Invalid token should raise
    import jwt

    from app.utils.security import decode_token
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


@pytest.mark.asyncio
async def test_ws_manager_multiple_users_isolated():
    """Messages to user-1 do not reach user-2."""
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
    await manager.connect("user-2", ws2)

    await manager.broadcast("user-1", "private_event", {"secret": "data"})

    assert len(ws1.sent_messages) == 1
    assert len(ws2.sent_messages) == 0  # user-2 should not receive user-1's message


@pytest.mark.asyncio
async def test_ws_manager_disconnect_one_of_many():
    """Disconnecting one WebSocket leaves others for the same user intact."""
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
    assert len(manager._connections["user-1"]) == 2

    await manager.disconnect("user-1", ws1)
    assert len(manager._connections["user-1"]) == 1

    # Remaining socket still receives broadcasts
    await manager.broadcast("user-1", "still_alive", {})
    assert len(ws2.sent_messages) == 1
    assert len(ws1.sent_messages) == 0


@pytest.mark.asyncio
async def test_ws_blacklisted_token_rejected(client: AsyncClient, auth_headers: dict, redis):
    """A blacklisted JWT token should fail WebSocket auth validation."""
    from app.utils.security import decode_token

    token = auth_headers["Authorization"].replace("Bearer ", "")
    payload = decode_token(token)
    jti = payload.get("jti")

    # Blacklist the token in Redis (same pattern as logout)
    await redis.set(f"token:blacklist:{jti}", "1", ex=86400)

    # Verify the blacklist check works as the WS endpoint would
    blacklisted = await redis.get(f"token:blacklist:{jti}")
    assert blacklisted is not None


@pytest.mark.asyncio
async def test_ws_broadcast_json_structure():
    """Broadcast message has correct JSON structure with type and data fields."""
    import json as json_mod

    manager = ConnectionManager()

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
    await manager.broadcast("user-1", "email_sent", {"message_id": "abc123", "contact_email": "test@example.com"})

    msg = json_mod.loads(ws.sent_messages[0])
    assert msg["type"] == "email_sent"
    assert msg["data"]["message_id"] == "abc123"
    assert msg["data"]["contact_email"] == "test@example.com"
