"""CLI entry point for the scheduler (Phase 8)."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from config.config import Config
from scheduler.job_scraper_scheduler import JobScraperScheduler


def _build_parser() -> argparse.ArgumentParser:
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
    """Run the scheduler loop until interrupted."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = Config()

    errors = config.validate()
    if errors:
        for error in errors:
            print(f"Config error: {error}")
        return 1

    scheduler = JobScraperScheduler(config=config, poll_interval_minutes=args.interval)

    try:
        scheduler.run_forever()
    except KeyboardInterrupt:
        scheduler.request_stop()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
