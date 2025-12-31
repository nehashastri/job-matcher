"""
Unit tests for logging utilities (Phase 0)
"""

import logging

from config.logging_utils import (
    ConsoleFormatter,
    get_logger,
    log_cycle_separator,
    log_job_decision,
    log_phase_start,
    setup_logging,
)


class TestLoggingSetup:
    """Test logging setup and configuration"""

    def test_setup_logging_creates_log_dir(self, temp_dir):
        """Test that setup_logging creates the log directory"""
        log_dir = temp_dir / "logs"

        setup_logging(log_dir=str(log_dir), enable_console=False)

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_setup_logging_creates_log_file(self, temp_dir):
        """Test that setup_logging creates the log file"""
        log_dir = temp_dir / "logs"
        log_file = "test.log"

        setup_logging(log_dir=str(log_dir), log_file=log_file, enable_console=False)

        log_path = log_dir / log_file
        assert log_path.exists()

    def test_setup_logging_respects_log_level(self, temp_dir):
        """Test that setup_logging respects the log level"""
        log_dir = temp_dir / "logs"

        logger = setup_logging(log_dir=str(log_dir), log_level="WARNING", enable_console=False)

        assert logger.level == logging.WARNING

    def test_setup_logging_writes_to_file(self, temp_dir):
        """Test that logging actually writes to the file"""
        log_dir = temp_dir / "logs"
        log_file = "test.log"

        setup_logging(log_dir=str(log_dir), log_file=log_file, enable_console=False)
        logger = logging.getLogger("test")

        test_message = "Test log message"
        logger.info(test_message)

        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()

        log_path = log_dir / log_file
        content = log_path.read_text(encoding="utf-8")

        assert test_message in content


class TestStructuredFormatter:
    """Test structured log formatting"""

    def test_structured_formatter_adds_category(self, temp_dir):
        """Test that StructuredFormatter adds category labels"""
        log_dir = temp_dir / "logs"
        log_file = "test.log"

        setup_logging(log_dir=str(log_dir), log_file=log_file, enable_console=False)

        # Test different logger categories
        auth_logger = logging.getLogger("job_scraper.auth")
        scrape_logger = logging.getLogger("job_scraper.scrape")

        auth_logger.info("Auth test message")
        scrape_logger.info("Scrape test message")

        # Force flush
        for handler in logging.getLogger().handlers:
            handler.flush()

        log_path = log_dir / log_file
        content = log_path.read_text(encoding="utf-8")

        assert "[LOGIN]" in content
        assert "[SCRAPE]" in content

    def test_console_formatter_removes_emojis(self):
        """Test that ConsoleFormatter removes emoji characters"""
        formatter = ConsoleFormatter("[%(levelname)s] %(message)s")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test 🔑 message ✅",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        # Emojis should be removed
        assert "🔑" not in formatted
        assert "✅" not in formatted
        assert "Test" in formatted
        assert "message" in formatted


class TestLoggingHelpers:
    """Test logging helper functions"""

    def test_log_cycle_separator_with_number(self, temp_dir, caplog):
        """Test log_cycle_separator with cycle number"""
        log_dir = temp_dir / "logs"
        setup_logging(log_dir=str(log_dir), enable_console=False)
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        logger.propagate = True

        log_cycle_separator(logger, cycle_num=1)

        for handler in logging.getLogger().handlers:
            handler.flush()

        log_file = log_dir / "job_finder.log"
        content = log_file.read_text(encoding="utf-8")
        assert "START OF CYCLE 1" in content
        assert "=" in content

    def test_log_cycle_separator_without_number(self, temp_dir, caplog):
        """Test log_cycle_separator without cycle number"""
        log_dir = temp_dir / "logs"
        setup_logging(log_dir=str(log_dir), enable_console=False)
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        logger.propagate = True

        log_cycle_separator(logger)

        for handler in logging.getLogger().handlers:
            handler.flush()

        log_file = log_dir / "job_finder.log"
        content = log_file.read_text(encoding="utf-8")
        assert "END OF CYCLE" in content

    def test_log_phase_start(self, temp_dir, caplog):
        """Test log_phase_start"""
        log_dir = temp_dir / "logs"
        setup_logging(log_dir=str(log_dir), enable_console=False)
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        logger.propagate = True

        log_phase_start(logger, "Authentication")

        for handler in logging.getLogger().handlers:
            handler.flush()

        log_file = log_dir / "job_finder.log"
        content = log_file.read_text(encoding="utf-8")
        assert "AUTHENTICATION" in content
        assert "---" in content

    def test_log_job_decision_with_score(self, temp_dir, caplog):
        """Test log_job_decision with score"""
        log_dir = temp_dir / "logs"
        setup_logging(log_dir=str(log_dir), enable_console=False)
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        logger.propagate = True

        log_job_decision(
            logger,
            job_id="12345",
            job_title="Software Engineer",
            company="Test Corp",
            decision="ACCEPT",
            reason="High match",
            score=9.5,
        )

        for handler in logging.getLogger().handlers:
            handler.flush()

        log_file = log_dir / "job_finder.log"
        content = log_file.read_text(encoding="utf-8")
        assert "12345" in content
        assert "Software Engineer" in content
        assert "Test Corp" in content
        assert "ACCEPT" in content
        assert "9.5" in content

    def test_log_job_decision_without_score(self, temp_dir, caplog):
        """Test log_job_decision without score"""
        log_dir = temp_dir / "logs"
        setup_logging(log_dir=str(log_dir), enable_console=False)
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        logger.propagate = True

        log_job_decision(
            logger,
            job_id="12345",
            job_title="Software Engineer",
            company="Test Corp",
            decision="REJECT",
            reason="Blocklist hit",
        )

        for handler in logging.getLogger().handlers:
            handler.flush()

        log_file = log_dir / "job_finder.log"
        content = log_file.read_text(encoding="utf-8")
        assert "12345" in content
        assert "REJECT" in content
        assert "Blocklist hit" in content

    def test_get_logger_structured(self):
        """Test get_logger returns a structlog logger when structured=True"""
        logger = get_logger("test_module", structured=True)

        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")

    def test_get_logger_stdlib(self):
        """Test get_logger returns stdlib logger when structured=False"""
        logger = get_logger("test_module", structured=False)

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"
