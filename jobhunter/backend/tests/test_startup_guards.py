import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_default_jwt_secret_blocks_startup():
    """App must refuse to start with the default JWT secret."""
    from app.main import _JWT_DEFAULT

    with patch("app.main.settings") as mock_settings:
        mock_settings.JWT_SECRET = _JWT_DEFAULT
        mock_settings.SENTRY_DSN = ""
        mock_settings.APP_NAME = "test"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        from app.main import lifespan, app

        with pytest.raises(SystemExit):
            async with lifespan(app):
                pass
