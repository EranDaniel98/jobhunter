import pytest
from datetime import datetime, timezone
from app.services.invite_service import create_system_invite


@pytest.mark.asyncio
async def test_create_system_invite(db_session):
    """System invite has no invited_by and stores email."""
    invite = await create_system_invite(db_session, "test@example.com")

    assert invite.code is not None
    assert len(invite.code) > 0
    assert invite.invited_by_id is None
    assert invite.email == "test@example.com"
    assert invite.is_used is False
    assert invite.expires_at > datetime.now(timezone.utc)
