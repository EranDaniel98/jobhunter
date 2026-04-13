"""In-process mock Resend email client for load testing.

Simulates realistic send latency and returns synthetic message IDs. Performs
no network I/O. Used only when LOADTEST_MODE=True.
"""
import asyncio
import uuid


class MockResendClient:
    """Mock implementation of EmailClientProtocol."""

    _LATENCY = 0.2

    async def send(
        self,
        to: str,
        from_email: str,
        subject: str,
        body: str,
        tags: list[str] | None = None,
        headers: dict | None = None,
        attachments: list[dict] | None = None,
        reply_to: str | None = None,
    ) -> dict:
        await asyncio.sleep(self._LATENCY)
        return {"id": f"mock_{uuid.uuid4().hex}"}

    def verify_webhook(self, payload: bytes, headers: dict) -> dict:
        # Deterministic no-op webhook parse for load testing.
        return {"type": "email.delivered", "data": {"email_id": "mock"}}
