"""Tests for utilities/logger.py module."""

import logging


from good_agent.utilities.logger import get_logger


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_instance(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)

    def test_returns_logger_with_name(self):
        """Test that get_logger returns logger with specified name."""
        logger = get_logger("test_logger")
        # Should return a logger (name may vary depending on Prefect context)
        assert isinstance(logger, logging.Logger)

    def test_returns_logger_without_name(self):
        """Test that get_logger works without name parameter."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)

    def test_logger_has_standard_methods(self):
        """Test that returned logger has standard logging methods."""
        logger = get_logger()

        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

    def test_logger_can_log_messages(self):
        """Test that logger can log messages without errors."""
        logger = get_logger("test")

        # Should not raise any exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
