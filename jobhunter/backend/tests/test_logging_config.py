"""Tests for setup_logging() in app/middleware/logging_config.py."""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from app.middleware.logging_config import setup_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    """Preserve root logger state across tests."""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = root.handlers[:]
    yield
    root.level = original_level
    root.handlers = original_handlers


def test_setup_logging_calls_structlog_configure():
    """setup_logging() must call structlog.configure() with processors list."""
    with patch("app.middleware.logging_config.structlog") as mock_structlog:
        mock_structlog.configure = MagicMock()
        # Provide enough attr stubs so the call doesn't blow up
        mock_structlog.contextvars.merge_contextvars = MagicMock()
        mock_structlog.stdlib.filter_by_level = MagicMock()
        mock_structlog.stdlib.add_logger_name = MagicMock()
        mock_structlog.stdlib.add_log_level = MagicMock()
        mock_structlog.stdlib.PositionalArgumentsFormatter = MagicMock()
        mock_structlog.processors.TimeStamper = MagicMock(return_value=MagicMock())
        mock_structlog.processors.StackInfoRenderer = MagicMock()
        mock_structlog.processors.format_exc_info = MagicMock()
        mock_structlog.processors.UnicodeDecoder = MagicMock()
        mock_structlog.processors.JSONRenderer = MagicMock(return_value=MagicMock())
        mock_structlog.stdlib.BoundLogger = MagicMock()
        mock_structlog.stdlib.LoggerFactory = MagicMock(return_value=MagicMock())

        setup_logging()

        mock_structlog.configure.assert_called_once()
        kwargs = mock_structlog.configure.call_args.kwargs
        assert "processors" in kwargs
        assert kwargs["wrapper_class"] == mock_structlog.stdlib.BoundLogger
        assert kwargs["context_class"] is dict
        assert kwargs["cache_logger_on_first_use"] is True


def test_setup_logging_sets_root_log_level():
    """setup_logging() sets the root logger level from settings.LOG_LEVEL."""
    with patch("app.middleware.logging_config.settings") as mock_settings:
        mock_settings.LOG_LEVEL = "DEBUG"
        setup_logging()

    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_sets_info_level_by_default():
    """setup_logging() with LOG_LEVEL=INFO results in INFO level on root logger."""
    with patch("app.middleware.logging_config.settings") as mock_settings:
        mock_settings.LOG_LEVEL = "INFO"
        setup_logging()

    root = logging.getLogger()
    assert root.level == logging.INFO


def test_setup_logging_replaces_handlers_with_single_stdout_handler():
    """setup_logging() replaces existing handlers with a single StreamHandler on stdout."""
    # Pre-populate handlers to verify replacement
    root = logging.getLogger()
    root.addHandler(logging.NullHandler())
    root.addHandler(logging.NullHandler())

    setup_logging()

    assert len(root.handlers) == 1
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout


def test_setup_logging_quiets_uvicorn_access():
    """setup_logging() sets uvicorn.access to WARNING."""
    setup_logging()
    assert logging.getLogger("uvicorn.access").level == logging.WARNING


def test_setup_logging_quiets_sqlalchemy_engine():
    """setup_logging() sets sqlalchemy.engine to WARNING."""
    setup_logging()
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


def test_setup_logging_warning_level():
    """setup_logging() with LOG_LEVEL=WARNING sets WARNING on the root logger."""
    with patch("app.middleware.logging_config.settings") as mock_settings:
        mock_settings.LOG_LEVEL = "WARNING"
        setup_logging()

    root = logging.getLogger()
    assert root.level == logging.WARNING
