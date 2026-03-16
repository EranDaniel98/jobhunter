import asyncio
from functools import partial

import resend
import structlog
from svix.webhooks import Webhook

from app.config import settings

logger = structlog.get_logger()


class ResendClient:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY
        self._webhook_secret = settings.RESEND_WEBHOOK_SECRET

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
        params = {
            "from": from_email,
            "to": [to],
            "subject": subject,
            "text": body,
        }
        if tags:
            params["tags"] = [{"name": t, "value": "true"} for t in tags]
        if headers:
            params["headers"] = headers
        if attachments:
            params["attachments"] = attachments
        if reply_to:
            params["reply_to"] = [reply_to]

        # Resend SDK is synchronous - run in executor
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(resend.Emails.send, params))
        result_dict = dict(result) if not isinstance(result, dict) else result
        logger.info("email_sent_via_resend", to=to, message_id=result_dict.get("id"))
        return result_dict

    def verify_webhook(self, payload: bytes, headers: dict) -> dict:
        wh = Webhook(self._webhook_secret)
        return wh.verify(payload, headers)
