"""Tests for daily OpenAI cost tracking and circuit breaker."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.services.cost_service import (
    INPUT_COST_PER_TOKEN,
    OUTPUT_COST_PER_TOKEN,
    _today_key,
    check_budget,
    record_usage,
)


def test_today_key_format():
    """Key should follow openai:daily_cost:YYYY-MM-DD pattern."""
    key = _today_key()
    assert key.startswith("openai:daily_cost:")
    # Date part should be 10 chars (YYYY-MM-DD)
    date_part = key.split(":")[-1]
    assert len(date_part) == 10


def test_pricing_constants():
    """Verify GPT-4o pricing constants are reasonable."""
    assert INPUT_COST_PER_TOKEN == 0.025
    assert OUTPUT_COST_PER_TOKEN == 0.1
    # Output tokens should cost more than input tokens
    assert OUTPUT_COST_PER_TOKEN > INPUT_COST_PER_TOKEN


@pytest.mark.asyncio
async def test_check_budget_passes_when_under_limit():
    """No exception when daily cost is under the limit."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "100"  # 1 cent (100 hundredths), way under 5000 cents limit

    with (
        patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
        patch("app.services.cost_service.settings") as mock_settings,
    ):
        mock_settings.DAILY_OPENAI_COST_LIMIT_CENTS = 5000
        await check_budget()  # Should not raise


@pytest.mark.asyncio
async def test_check_budget_raises_503_when_over_limit():
    """HTTP 503 raised when daily cost exceeds limit."""
    mock_redis = AsyncMock()
    # 500000 hundredths = 5000 cents = $50
    mock_redis.get.return_value = "500000"

    with (
        patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
        patch("app.services.cost_service.settings") as mock_settings,
    ):
        mock_settings.DAILY_OPENAI_COST_LIMIT_CENTS = 5000
        with pytest.raises(HTTPException) as exc_info:
            await check_budget()
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_check_budget_passes_when_no_key():
    """No exception when Redis key doesn't exist yet (first call of the day)."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
        await check_budget()  # Should not raise


@pytest.mark.asyncio
async def test_check_budget_raises_503_on_redis_failure():
    """If Redis is down, raise 503 to prevent untracked usage."""
    with patch("app.infrastructure.redis_client.get_redis", side_effect=Exception("Redis down")):
        with pytest.raises(HTTPException) as exc_info:
            await check_budget()
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_record_usage_returns_cost():
    """record_usage should return estimated cost in hundredths of a cent."""
    mock_redis = AsyncMock()

    with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
        cost = await record_usage(1000, 500)

    expected = int(1000 * INPUT_COST_PER_TOKEN + 500 * OUTPUT_COST_PER_TOKEN)
    assert cost == expected


@pytest.mark.asyncio
async def test_record_usage_zero_tokens():
    """Zero tokens should return 0 cost."""
    cost = await record_usage(0, 0)
    assert cost == 0


@pytest.mark.asyncio
async def test_record_usage_increments_redis():
    """record_usage should INCRBY the daily key in Redis."""
    mock_redis = AsyncMock()

    with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
        await record_usage(1000, 500)

    mock_redis.incrby.assert_called_once()
    mock_redis.expire.assert_called_once()


@pytest.mark.asyncio
async def test_record_usage_graceful_on_redis_failure():
    """If Redis INCRBY fails, still return cost (graceful degradation)."""
    mock_redis = AsyncMock()
    mock_redis.incrby.side_effect = Exception("Redis down")

    with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
        cost = await record_usage(1000, 500)

    assert cost > 0  # Still returns cost even though Redis failed


@pytest.mark.asyncio
async def test_record_usage_with_candidate_id_calls_per_user():
    """When candidate_id is provided, _record_per_user is called."""
    mock_redis = AsyncMock()

    with (
        patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
        patch("app.services.cost_service._record_per_user", new_callable=AsyncMock) as mock_record,
    ):
        await record_usage(
            1000,
            500,
            candidate_id="abc-123",
            endpoint="/api/v1/interview/prep",
            model="gpt-4o",
        )

    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["candidate_id"] == "abc-123"
    assert call_kwargs["endpoint"] == "/api/v1/interview/prep"


@pytest.mark.asyncio
async def test_record_usage_per_user_failure_doesnt_crash():
    """If per-user DB insert fails, record_usage still succeeds."""
    mock_redis = AsyncMock()

    with (
        patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
        patch(
            "app.services.cost_service._record_per_user",
            new_callable=AsyncMock,
            side_effect=Exception("DB down"),
        ),
    ):
        cost = await record_usage(1000, 500, candidate_id="abc-123")

    assert cost > 0


def test_concurrency_module_exists():
    """Verify concurrency semaphore module can be imported."""
    from app.services.concurrency import acquire_ai_slot

    assert acquire_ai_slot is not None


@pytest.mark.asyncio
async def test_concurrency_semaphore_allows_within_limit():
    """Semaphore should allow up to 3 concurrent slots."""
    from app.services.concurrency import acquire_ai_slot

    async with acquire_ai_slot("test-user-1"):
        pass  # Should succeed without error


@pytest.mark.asyncio
async def test_concurrency_semaphore_rejects_over_limit():
    """4th concurrent request should get 429."""

    from app.services.concurrency import _get_semaphore, acquire_ai_slot

    user_id = "test-overload-user"

    # Acquire all 3 slots
    sem = _get_semaphore(user_id)
    await sem.acquire()
    await sem.acquire()
    await sem.acquire()

    # 4th should timeout and raise 429
    with pytest.raises(HTTPException) as exc_info:
        async with acquire_ai_slot(user_id):
            pass
    assert exc_info.value.status_code == 429

    # Release slots
    sem.release()
    sem.release()
    sem.release()


def test_billing_model_exists():
    """Verify ApiUsageRecord model can be imported."""
    from app.models.billing import ApiUsageRecord

    assert ApiUsageRecord.__tablename__ == "api_usage"


def test_rls_helpers():
    """Verify RLS helper functions exist in tenant middleware."""
    from app.middleware.tenant import (
        _has_candidate_id_column,
        current_tenant_id,
        install_rls_listener,
    )

    assert current_tenant_id.get() is None
    assert install_rls_listener is not None
    assert _has_candidate_id_column is not None


def test_rls_listener_skips_when_disabled():
    """install_rls_listener should be a no-op when ENABLE_RLS=False."""
    from unittest.mock import MagicMock

    from app.middleware.tenant import install_rls_listener

    mock_engine = MagicMock()

    with patch("app.middleware.tenant.settings") as mock_settings:
        mock_settings.ENABLE_RLS = False
        install_rls_listener(mock_engine)

    # Should not have installed any event listener
    mock_engine.sync_engine.assert_not_called()


def test_rls_listener_installs_when_enabled():
    """install_rls_listener should register an event listener when ENABLE_RLS=True."""
    from unittest.mock import MagicMock

    from app.middleware.tenant import install_rls_listener

    mock_engine = MagicMock()

    with (
        patch("app.middleware.tenant.settings") as mock_settings,
        patch("app.middleware.tenant.event") as mock_event,
    ):
        mock_settings.ENABLE_RLS = True
        install_rls_listener(mock_engine)

    from sqlalchemy.orm import Session

    mock_event.listens_for.assert_called_once_with(Session, "do_orm_execute")


def test_has_candidate_id_column_true():
    """_has_candidate_id_column should return True for models with candidate_id."""
    from unittest.mock import MagicMock

    from app.middleware.tenant import _has_candidate_id_column

    mock_mapper = MagicMock()
    col1 = MagicMock()
    col1.key = "id"
    col2 = MagicMock()
    col2.key = "candidate_id"
    mock_mapper.columns = [col1, col2]

    assert _has_candidate_id_column(mock_mapper) is True


def test_has_candidate_id_column_false():
    """_has_candidate_id_column should return False for models without candidate_id."""
    from unittest.mock import MagicMock

    from app.middleware.tenant import _has_candidate_id_column

    mock_mapper = MagicMock()
    col1 = MagicMock()
    col1.key = "id"
    col2 = MagicMock()
    col2.key = "name"
    mock_mapper.columns = [col1, col2]

    assert _has_candidate_id_column(mock_mapper) is False


def test_has_candidate_id_column_handles_exception():
    """_has_candidate_id_column should return False on exception."""
    from unittest.mock import MagicMock, PropertyMock

    from app.middleware.tenant import _has_candidate_id_column

    mock_mapper = MagicMock()
    type(mock_mapper).columns = PropertyMock(side_effect=Exception("broken"))

    assert _has_candidate_id_column(mock_mapper) is False


def test_current_tenant_id_set_and_get():
    """current_tenant_id contextvar should support set/get."""
    from app.middleware.tenant import current_tenant_id

    assert current_tenant_id.get() is None
    token = current_tenant_id.set("test-tenant-123")
    assert current_tenant_id.get() == "test-tenant-123"
    current_tenant_id.reset(token)
    assert current_tenant_id.get() is None


def test_forgot_password_public_path():
    """Forgot-password and reset-password should be in PUBLIC_PATHS."""
    from app.middleware.tenant import PUBLIC_PATHS

    assert "/api/v1/auth/forgot-password" in PUBLIC_PATHS
    assert "/api/v1/auth/reset-password" in PUBLIC_PATHS


def test_create_reset_token():
    """create_reset_token should produce a valid JWT with type=reset."""
    import jwt as pyjwt

    from app.utils.security import create_reset_token

    with patch("app.utils.security.settings") as mock_settings:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        token = create_reset_token("candidate-abc")

    payload = pyjwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == "candidate-abc"
    assert payload["type"] == "reset"
    assert "exp" in payload


def test_config_has_new_settings():
    """Config should have DAILY_OPENAI_COST_LIMIT_CENTS and ENABLE_RLS."""
    from app.config import Settings

    s = Settings(
        DATABASE_URL="postgresql+asyncpg://x:x@localhost/x",
        REDIS_URL="redis://localhost",
        JWT_SECRET="not-default",
        OPENAI_API_KEY="sk-test",
    )
    assert hasattr(s, "DAILY_OPENAI_COST_LIMIT_CENTS")
    assert hasattr(s, "ENABLE_RLS")
    assert s.DAILY_OPENAI_COST_LIMIT_CENTS == 5000
    assert s.ENABLE_RLS is False
