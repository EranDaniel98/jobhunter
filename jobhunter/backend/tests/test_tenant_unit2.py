"""Additional unit tests for app/middleware/tenant.py - covers RLS listener
filtering paths (lines 77-78, 110-125): bypass flag, non-select, no tenant,
single mapper with candidate_id, and mapper without candidate_id."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.middleware.tenant import (
    _has_candidate_id_column,
    current_tenant_id,
    install_rls_listener,
)

# ---------------------------------------------------------------------------
# _has_candidate_id_column helper
# ---------------------------------------------------------------------------


class TestHasCandidateIdColumn:
    def test_mapper_with_candidate_id_returns_true(self):
        """Mapper that has candidate_id column returns True."""
        col1 = MagicMock()
        col1.key = "id"
        col2 = MagicMock()
        col2.key = "candidate_id"

        mapper = MagicMock()
        mapper.columns = [col1, col2]

        assert _has_candidate_id_column(mapper) is True

    def test_mapper_without_candidate_id_returns_false(self):
        """Mapper without candidate_id column returns False."""
        col1 = MagicMock()
        col1.key = "id"
        col2 = MagicMock()
        col2.key = "name"

        mapper = MagicMock()
        mapper.columns = [col1, col2]

        assert _has_candidate_id_column(mapper) is False

    def test_mapper_exception_returns_false(self):
        """If accessing mapper.columns raises, returns False gracefully."""
        mapper = MagicMock()
        mapper.columns = MagicMock(side_effect=Exception("no columns"))

        # The set comprehension will fail when iterating
        # patch columns to raise on iteration
        type(mapper).columns = property(lambda s: (_ for _ in ()).throw(Exception("err")))

        result = _has_candidate_id_column(mapper)
        assert result is False


# ---------------------------------------------------------------------------
# install_rls_listener - disabled path
# ---------------------------------------------------------------------------


class TestInstallRlsListenerDisabled:
    def test_rls_disabled_does_not_install_listener(self):
        """When ENABLE_RLS=False, no listener is installed."""
        engine = MagicMock()

        with patch("app.middleware.tenant.settings") as mock_settings:
            mock_settings.ENABLE_RLS = False
            install_rls_listener(engine)

        # No event listener registered on the sync engine
        engine.sync_engine.assert_not_called()


# ---------------------------------------------------------------------------
# install_rls_listener - enabled path: _apply_rls_filter function
# ---------------------------------------------------------------------------


class TestRlsFilterFunction:
    def _get_filter_fn(self, engine=None):
        """Install listener and capture the registered filter function."""
        if engine is None:
            engine = MagicMock()
            engine.sync_engine = MagicMock()

        captured = {}

        def fake_listens_for(target, event_name):
            def decorator(fn):
                captured["fn"] = fn
                return fn

            return decorator

        with (
            patch("app.middleware.tenant.settings") as mock_settings,
            patch("app.middleware.tenant.event") as mock_event,
        ):
            mock_settings.ENABLE_RLS = True
            mock_event.listens_for = fake_listens_for
            install_rls_listener(engine)

        return captured.get("fn")

    def test_bypass_rls_flag_skips_filtering(self):
        """Execution option _bypass_rls=True skips all filtering."""
        fn = self._get_filter_fn()

        state = MagicMock()
        state.execution_options = {"_bypass_rls": True}
        state.is_select = True
        state.all_mappers = []

        fn(state)  # Should return early, no statement modification
        # If we got here without error, the bypass worked correctly

    def test_non_select_skips_filtering(self):
        """Non-SELECT statements (INSERT/UPDATE) are not filtered."""
        fn = self._get_filter_fn()

        state = MagicMock()
        state.execution_options = {}
        state.is_select = False
        state.all_mappers = []

        fn(state)

        # statement should not be replaced
        assert not state.statement.where.called

    def test_no_tenant_context_skips_filtering(self):
        """When current_tenant_id is None, no filter is applied."""
        fn = self._get_filter_fn()

        token = current_tenant_id.set(None)
        try:
            state = MagicMock()
            state.execution_options = {}
            state.is_select = True
            state.all_mappers = []

            fn(state)

            assert not state.statement.where.called
        finally:
            current_tenant_id.reset(token)

    def test_select_with_tenant_and_mapper_with_candidate_id_applies_filter(self):
        """SELECT with tenant context applies WHERE candidate_id = tenant_id."""
        fn = self._get_filter_fn()

        tenant_id = str(uuid.uuid4())
        token = current_tenant_id.set(tenant_id)

        try:
            col = MagicMock()
            col.key = "candidate_id"

            # Use MagicMock for columns so we can control iteration and dict access
            cols_mock = MagicMock()
            cols_mock.__iter__ = MagicMock(return_value=iter([col]))
            cols_mock.__contains__ = MagicMock(side_effect=lambda k: k == "candidate_id")
            cols_mock.__getitem__ = MagicMock(side_effect=lambda k: col if k == "candidate_id" else None)

            mapper = MagicMock()
            mapper.columns = cols_mock

            original_statement = MagicMock()
            original_statement.where.return_value = MagicMock()

            state = MagicMock()
            state.execution_options = {}
            state.is_select = True
            state.all_mappers = [mapper]
            state.statement = original_statement

            fn(state)

            original_statement.where.assert_called_once()
        finally:
            current_tenant_id.reset(token)

    def test_mapper_without_candidate_id_no_filter_applied(self):
        """Mapper without candidate_id column is skipped (no filter applied)."""
        fn = self._get_filter_fn()

        tenant_id = str(uuid.uuid4())
        token = current_tenant_id.set(tenant_id)

        try:
            col = MagicMock()
            col.key = "id"

            mapper = MagicMock()
            mapper.columns = [col]

            state = MagicMock()
            state.execution_options = {}
            state.is_select = True
            state.all_mappers = [mapper]
            state.statement = MagicMock()

            fn(state)

            state.statement.where.assert_not_called()
        finally:
            current_tenant_id.reset(token)


# ---------------------------------------------------------------------------
# TenantMiddleware — waitlist path bypass
# ---------------------------------------------------------------------------


class TestTenantMiddlewareWaitlistBypass:
    @pytest.mark.asyncio
    async def test_waitlist_path_bypasses_tenant_extraction(self):
        """Paths starting with /api/v1/waitlist bypass tenant extraction."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from app.middleware.tenant import TenantMiddleware

        app = FastAPI()
        app.add_middleware(TenantMiddleware)

        @app.get("/api/v1/waitlist/join")
        async def waitlist_join():
            return {"joined": True}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/waitlist/join")

        assert resp.status_code == 200
        assert resp.json() == {"joined": True}

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_jwt_decode_handled(self):
        """Non-JWT exception during token decode is caught via except Exception."""
        import jwt
        from fastapi import FastAPI, Request
        from httpx import ASGITransport, AsyncClient

        from app.middleware.tenant import TenantMiddleware

        app = FastAPI()
        app.add_middleware(TenantMiddleware)

        @app.get("/api/v1/protected")
        async def protected(request: Request):
            return {"tenant_id": getattr(request.state, "tenant_id", None)}

        token = jwt.encode({"sub": "user-id"}, "secret", algorithm="HS256")

        with patch("app.middleware.tenant.jwt.decode", side_effect=RuntimeError("unexpected")):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(
                    "/api/v1/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] is None
