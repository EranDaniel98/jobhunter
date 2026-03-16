"""Tests for ResendClient - wraps Resend SDK for email sending and webhook verification."""

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.resend_client import ResendClient


@pytest.fixture
def resend_client():
    """Return a ResendClient with mocked settings."""
    with (
        patch("app.infrastructure.resend_client.settings") as mock_settings,
        patch("app.infrastructure.resend_client.resend") as mock_resend,
    ):
        mock_settings.RESEND_API_KEY = "re_test_key"
        mock_settings.RESEND_WEBHOOK_SECRET = "whsec_test_secret"
        client = ResendClient()
        yield client, mock_resend


@pytest.mark.asyncio
async def test_send_basic(resend_client):
    """send() calls resend.Emails.send with required params."""
    client, mock_resend = resend_client
    mock_resend.Emails.send.return_value = {"id": "email-123"}

    result = await client.send(
        to="alice@example.com",
        from_email="noreply@example.com",
        subject="Hello",
        body="World",
    )

    assert result == {"id": "email-123"}
    mock_resend.Emails.send.assert_called_once()
    call_params = mock_resend.Emails.send.call_args[0][0]
    assert call_params["to"] == ["alice@example.com"]
    assert call_params["from"] == "noreply@example.com"
    assert call_params["subject"] == "Hello"
    assert call_params["text"] == "World"


@pytest.mark.asyncio
async def test_send_with_optional_fields(resend_client):
    """send() includes optional fields when provided."""
    client, mock_resend = resend_client
    mock_resend.Emails.send.return_value = {"id": "email-456"}

    result = await client.send(
        to="bob@example.com",
        from_email="noreply@example.com",
        subject="Test",
        body="Body",
        tags=["promo", "test"],
        headers={"X-Custom": "value"},
        attachments=[{"filename": "file.pdf", "content": "base64data"}],
        reply_to="support@example.com",
    )

    assert result == {"id": "email-456"}
    call_params = mock_resend.Emails.send.call_args[0][0]
    assert call_params["tags"] == [{"name": "promo", "value": "true"}, {"name": "test", "value": "true"}]
    assert call_params["headers"] == {"X-Custom": "value"}
    assert call_params["attachments"] == [{"filename": "file.pdf", "content": "base64data"}]
    assert call_params["reply_to"] == ["support@example.com"]


@pytest.mark.asyncio
async def test_send_without_optional_fields(resend_client):
    """send() omits optional keys when not provided."""
    client, mock_resend = resend_client
    mock_resend.Emails.send.return_value = {"id": "email-789"}

    await client.send(
        to="carol@example.com",
        from_email="noreply@example.com",
        subject="No extras",
        body="Plain",
    )

    call_params = mock_resend.Emails.send.call_args[0][0]
    assert "tags" not in call_params
    assert "headers" not in call_params
    assert "attachments" not in call_params
    assert "reply_to" not in call_params


@pytest.mark.asyncio
async def test_send_converts_non_dict_result(resend_client):
    """send() converts non-dict results (e.g. SDK objects) to dict."""
    client, mock_resend = resend_client

    class FakeResult:
        def __iter__(self):
            return iter([("id", "email-obj-123")])

    mock_resend.Emails.send.return_value = FakeResult()

    result = await client.send(
        to="dave@example.com",
        from_email="noreply@example.com",
        subject="Obj",
        body="Body",
    )
    assert result == {"id": "email-obj-123"}


@pytest.mark.asyncio
async def test_send_logs_success(resend_client):
    """send() logs a success message with the message ID."""
    client, mock_resend = resend_client
    mock_resend.Emails.send.return_value = {"id": "email-log-test"}

    with patch("app.infrastructure.resend_client.logger") as mock_logger:
        await client.send(
            to="eve@example.com",
            from_email="noreply@example.com",
            subject="Log test",
            body="Body",
        )

    mock_logger.info.assert_called_once_with(
        "email_sent_via_resend",
        to="eve@example.com",
        message_id="email-log-test",
    )


def test_verify_webhook_calls_svix(resend_client):
    """verify_webhook() uses Svix Webhook to verify the payload."""
    client, _mock_resend = resend_client

    mock_wh_instance = MagicMock()
    mock_wh_instance.verify.return_value = {"type": "email.delivered"}

    with patch("app.infrastructure.resend_client.Webhook") as mock_webhook_class:
        mock_webhook_class.return_value = mock_wh_instance

        payload = b'{"type":"email.delivered"}'
        headers = {"svix-id": "msg_123", "svix-signature": "sig", "svix-timestamp": "12345"}

        result = client.verify_webhook(payload, headers)

    mock_webhook_class.assert_called_once_with("whsec_test_secret")
    mock_wh_instance.verify.assert_called_once_with(payload, headers)
    assert result == {"type": "email.delivered"}


def test_verify_webhook_propagates_exception(resend_client):
    """verify_webhook() lets signature verification errors propagate."""
    client, _mock_resend = resend_client

    mock_wh_instance = MagicMock()
    mock_wh_instance.verify.side_effect = ValueError("invalid signature")

    with patch("app.infrastructure.resend_client.Webhook") as mock_webhook_class:
        mock_webhook_class.return_value = mock_wh_instance

        with pytest.raises(ValueError, match="invalid signature"):
            client.verify_webhook(b"payload", {})
