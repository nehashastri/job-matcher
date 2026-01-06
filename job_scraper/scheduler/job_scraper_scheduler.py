"""
Polling scheduler for the job scraper pipeline (Phase 8).

Runs the scrape → match → notify loop on an interval, supports dependency injection for tests.
Handles logging, configuration, and sleep interval management.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Callable

from config.config import LOG_DIR, Config
from config.logging_utils import log_cycle_separator, setup_logging

try:  # LinkedIn scraper is heavy; import lazily to keep tests fast
    from scraping.linkedin_scraper import LinkedInScraper
except Exception:  # pragma: no cover - best effort import guard
    LinkedInScraper = None  # type: ignore[assignment]

try:  # JobFinder pulls many deps; import lazily to keep import time low
    from app.job_finder import JobFinder
except Exception:  # pragma: no cover - optional for tests
    JobFinder = None  # type: ignore[assignment]


RoleRunner = Callable[[dict[str, Any]], Any]


class JobScraperScheduler:
    """
    Run the scrape → match → notify loop on an interval.

    The scheduler is intentionally dependency-injectable for tests; callers can supply a
    custom role runner function and sleep function to avoid touching Selenium or the
    filesystem during unit tests.
    Attributes:
        config (Config): Configuration instance
        interval_minutes (float): Polling interval in minutes
        sleep_fn (Callable[[float], None]): Sleep function (default: time.sleep)
        _stop_requested (bool): Flag to stop scheduler
        logger (logging.Logger): Logger instance
    """

    def __init__(
        self,
        config: Config | None = None,
        role_runner: RoleRunner | None = None,
        poll_interval_minutes: float | None = None,
        logger: logging.Logger | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        """
        Initialize JobScraperScheduler.
        Args:
            config (Config | None): Configuration instance
            role_runner (RoleRunner | None): Custom role runner function
            poll_interval_minutes (float | None): Polling interval override
            logger (logging.Logger | None): Logger instance
            sleep_fn (Callable[[float], None]): Sleep function
        """
        self.config = config or Config()
        self.interval_minutes = (
            poll_interval_minutes
            if poll_interval_minutes is not None
            else float(self.config.scrape_interval_minutes)
        )
        self.sleep_fn = sleep_fn
        self._stop_requested = False

        # Logging: write to a dedicated scheduler log while also honoring console output.
        log_file = LOG_DIR / "scheduler.log"
        self.logger = logger or setup_logging(
            log_dir=str(LOG_DIR),
            log_level=self.config.log_level,
            log_file=log_file.name,
            retention_days=self.config.log_file_retention_days,
            enable_console=True,
        )
        self.logger = self.logger.getChild("scheduler")

        # Allow tests to inject a lightweight runner; otherwise fall back to the real scraper.
        self.role_runner: RoleRunner = role_runner or self._jobfinder_role_runner
        self._job_finder = None  # type: ignore[var-annotated]

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------
    def request_stop(self) -> None:
        """Signal the scheduler loop to stop after the current cycle."""

        self._stop_requested = True

    def run_forever(self, max_cycles: int | None = None) -> None:
        """Run polling cycles until stopped or max_cycles is reached."""

        cycle_num = 1
        while not self._stop_requested:
            cycle_started_at = time.time()
            try:
                self.run_cycle(cycle_num)
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received; stopping scheduler")
                self.request_stop()
                break
            except Exception as exc:  # pragma: no cover - defensive catch
                self.logger.error("Scheduler cycle failed: %s", exc, exc_info=True)

            if max_cycles is not None and cycle_num >= max_cycles:
                break

            elapsed = time.time() - cycle_started_at
            sleep_seconds = max(self.interval_minutes * 60 - elapsed, 0)
            if sleep_seconds > 0 and not self._stop_requested:
                self.logger.info("Sleeping for %.1f minutes", sleep_seconds / 60)
                self.sleep_fn(sleep_seconds)

            cycle_num += 1

    def run_cycle(self, cycle_num: int = 1) -> list[dict[str, Any]]:
        """Run one full polling cycle across all enabled roles."""

        results: list[dict[str, Any]] = []
        log_cycle_separator(self.logger, cycle_num)

        roles = self.config.get_enabled_roles()
        if not roles:
            self.logger.warning("No enabled roles found in roles.json; nothing to do")
            log_cycle_separator(self.logger, None)
            return results

        for idx, role in enumerate(roles, start=1):
            role_label = (
                f"{role.get('title', 'Unknown')} ({role.get('location', 'Unknown')})"
            )
            self.logger.info("[ROLE %s/%s] %s", idx, len(roles), role_label)
            try:
                outcome = self.role_runner(role)
                results.append(
                    {
                        "role": role,
                        "status": "ok",
                        "outcome": outcome,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            except Exception as exc:
                self.logger.error("Role processing failed for %s: %s", role_label, exc)
                results.append(
                    {
                        "role": role,
                        "status": "error",
                        "error": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        log_cycle_separator(self.logger, None)
        return results

    # ---------------------------------------------------------------------
    # Default runner (real pipeline path)
    # ---------------------------------------------------------------------
    def _jobfinder_role_runner(self, role: dict[str, Any]) -> dict[str, Any]:
        """Use JobFinder to execute the full scrape→match→store→notify pipeline."""

        if JobFinder is None:  # pragma: no cover - guard for optional dependency
            raise RuntimeError("JobFinder is unavailable")

        # Cache a single JobFinder to reuse loaded resume/config across roles.
        if self._job_finder is None:
            self._job_finder = JobFinder()

        jobs = self._job_finder.scrape_jobs(max_applicants=self.config.max_applicants)

        return {
            "jobs_processed": len(jobs),
            "role": role.get("title", "Unknown"),
            "location": role.get("location", "Unknown"),
        }
