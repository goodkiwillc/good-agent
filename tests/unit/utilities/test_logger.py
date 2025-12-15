"""Tests for utilities/logger.py module."""

import logging
from typing import Any

from good_agent.utilities.logger import DEFAULT_FORMAT, configure_library_logging


class TestConfigureLibraryLogging:
    """Tests for configure_library_logging helper."""

    def test_configures_basic_logging_when_no_handlers(self, monkeypatch):
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)
        root_logger.handlers = []

        captured_kwargs: dict[str, Any] = {}

        def fake_basic_config(**kwargs):
            captured_kwargs.update(kwargs)

        monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

        try:
            configure_library_logging(level=logging.DEBUG, format="%(message)s", foo="bar")
        finally:
            root_logger.handlers = original_handlers

        assert captured_kwargs == {
            "level": logging.DEBUG,
            "format": "%(message)s",
            "foo": "bar",
        }

    def test_does_nothing_when_handlers_present(self, monkeypatch):
        root_logger = logging.getLogger()
        handler = logging.NullHandler()
        root_logger.addHandler(handler)

        called = False

        def fake_basic_config(**kwargs):
            nonlocal called
            called = True

        monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

        try:
            configure_library_logging()
        finally:
            root_logger.removeHandler(handler)

        assert called is False

    def test_defaults_are_respected_when_invoked(self, monkeypatch):
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)
        root_logger.handlers = []

        captured_kwargs: dict[str, Any] = {}

        def fake_basic_config(**kwargs):
            captured_kwargs.update(kwargs)

        monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

        try:
            configure_library_logging()
        finally:
            root_logger.handlers = original_handlers

        assert captured_kwargs == {"level": logging.INFO, "format": DEFAULT_FORMAT}
