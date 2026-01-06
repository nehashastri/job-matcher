"""
CLI entry point for the job scraper scheduler (Phase 8).

This module provides a command-line interface for starting and configuring the job scraper scheduler.
It uses argparse for argument parsing and loads configuration from config.Config.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from config.config import Config


def _build_parser() -> argparse.ArgumentParser:
    """
    Build and return the argument parser for CLI options.
    Returns:
        argparse.ArgumentParser: Configured parser for CLI arguments.
    """
    parser = argparse.ArgumentParser(description="Job scraper scheduler")
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=None,
        help="Polling interval in minutes (overrides SCRAPE_INTERVAL_MINUTES)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the scheduler loop until interrupted.
    Args:
        argv (Sequence[str] | None): Command-line arguments (optional).
    Returns:
        int: Exit code (0 for success, 1 for config error)
    """
    logger = logging.getLogger("cli.main")
    logger.info("Starting Job Scraper CLI entry point")

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = Config()
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        return 1

    logger.info("Configuration validated successfully. Ready to start scheduler.")
    # Here you would start the scheduler or main workflow
    return 0


if __name__ == "__main__":
    # Entry point for CLI execution
    sys.exit(main())
