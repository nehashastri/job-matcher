"""
Logging utilities with daily rotation and optional structlog support.

Provides custom formatters for structured logging, category labeling, and emoji removal for Windows consoles.
Includes setup functions for configuring logging handlers and formatters.
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, cast

import structlog


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter with structured output and category labels.
    Adds a category label to each log record based on logger name.
    """

    CATEGORY_MAP = {
        "auth": "LOGIN",
        "scrape": "SCRAPE",
        "filter": "FILTER",
        "match": "MATCH",
        "storage": "STORAGE",
        "network": "NETWORK",
        "email": "EMAIL",
        "scheduler": "SCHEDULER",
    }

    def format(self, record):
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}.format"
        )
        # Extract category from logger name
        category = "GENERAL"
        for key, label in self.CATEGORY_MAP.items():
            if key in record.name.lower():
                category = label
                break

        # Add category to record
        record.category = category

        # Format the message
        return super().format(record)


class ConsoleFormatter(StructuredFormatter):
    """
    Formatter that removes emojis for console output on Windows.
    Inherits category labeling from StructuredFormatter.
    """

    def format(self, record):
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}.format"
        )
        formatted = super().format(record)
        # Remove emoji characters that can't be displayed in some consoles
        import re

        formatted = re.sub(
            r"[\U0001F300-\U0001F9FF]|[\u2700-\u27BF]|[\u2600-\u26FF]|[\u2300-\u23FF]",
            "",
            formatted,
        )
        return formatted


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    log_file: str = "job_finder.log",
    retention_days: int = 30,
    enable_console: bool = True,
    enable_structlog: bool = True,
) -> logging.Logger:
    """
    Set up logging with daily rotation and structured formatting

    Args:
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Name of the log file
        retention_days: Number of days to retain log files
        enable_console: Whether to enable console output

    Returns:
        Configured root logger
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Convert log level string to constant
    level = getattr(logging, log_level.upper(), logging.INFO)

    # File handler with daily rotation
    file_handler = TimedRotatingFileHandler(
        filename=log_path / log_file,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_formatter = StructuredFormatter(
        "[%(asctime)s] [%(levelname)s] [%(category)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (optional)
    handlers: list[logging.Handler] = [file_handler]
    if enable_console:
        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setLevel(level)
        console_formatter = ConsoleFormatter(
            "[%(asctime)s] [%(levelname)s] [%(category)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Optional structlog configuration that routes through stdlib logging
    if enable_structlog:
        processors = [
            _add_category,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeEncoder(),
        ]

        structlog.configure(
            processors=cast(list[Any], processors),
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    return logging.getLogger()


def log_cycle_separator(logger: logging.Logger, cycle_num: int | None = None):
    """Log a visual separator for cycle start/end"""
    logging.getLogger(__name__).info(f"[ENTER] {__file__}::log_cycle_separator")
    if cycle_num is not None:
        logger.info(f"{'=' * 60}")
        logger.info(f"START OF CYCLE {cycle_num}")
        logger.info(f"{'=' * 60}")
    else:
        logger.info(f"{'=' * 60}")
        logger.info("END OF CYCLE")
        logger.info(f"{'=' * 60}")


def log_phase_start(logger: logging.Logger, phase_name: str):
    """Log the start of a processing phase"""
    logging.getLogger(__name__).info(f"[ENTER] {__file__}::log_phase_start")
    logger.info(f"--- {phase_name.upper()} ---")


def log_job_decision(
    logger: logging.Logger,
    job_id: str,
    job_title: str,
    company: str,
    decision: str,
    reason: str,
    score: float | None = None,
):
    """
    Log a structured job filtering/matching decision

    Args:
        logger: Logger instance
        job_id: Job ID
        job_title: Job title
        company: Company name
        decision: ACCEPT or REJECT
        reason: Reason for decision
        score: Match score (optional)
    """
    logging.getLogger(__name__).info(f"[ENTER] {__file__}::log_job_decision")
    score_str = f", score {score}" if score is not None else ""
    logger.info(
        f"Job {job_id} ({job_title} at {company}): {decision.upper()} - {reason}{score_str}"
    )


def get_logger(name: str, structured: bool = False) -> Any:
    """
    Get a logger for a specific module

    Args:
        name: Logger name (typically __name__)
        structured: If True, return structlog BoundLogger; otherwise stdlib logger

    Returns:
        Logger instance
    """
    logging.getLogger(__name__).info(f"[ENTER] {__file__}::get_logger")
    if structured:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def _add_category(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor that adds category based on logger name"""
    logger_name = event_dict.get("logger", "") or getattr(logger, "name", "")
    category = "GENERAL"
    name_lower = logger_name.lower() if isinstance(logger_name, str) else ""
    for key, label in StructuredFormatter.CATEGORY_MAP.items():
        if key in name_lower:
            category = label
            break

    event_dict.setdefault("category", category)
    return event_dict
