"""Phase 8 Tests: Scheduler orchestration and graceful looping."""

import logging
from typing import Any

from config.config import Config
from scheduler.job_scraper_scheduler import JobScraperScheduler


def _make_logger() -> logging.Logger:
    logger = logging.getLogger("test.scheduler")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def test_run_cycle_processes_enabled_roles(monkeypatch):
    """Enabled roles are processed; disabled roles are skipped."""

    config = Config()
    config.roles = [
        {"title": "A", "location": "X", "enabled": True},
        {"title": "B", "location": "Y", "enabled": False},
    ]

    calls: list[str] = []

    def runner(role: dict[str, Any]):
        calls.append(role["title"])
        return {"processed": role["title"]}

    scheduler = JobScraperScheduler(
        config=config,
        role_runner=runner,
        poll_interval_minutes=0.01,
        logger=_make_logger(),
        sleep_fn=lambda _s: None,
    )

    results = scheduler.run_cycle(cycle_num=1)

    assert calls == ["A"]
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["outcome"]["processed"] == "A"


def test_run_cycle_handles_role_errors(monkeypatch):
    """A failing role does not stop subsequent roles."""

    config = Config()
    config.roles = [
        {"title": "A", "location": "X", "enabled": True},
        {"title": "B", "location": "Y", "enabled": True},
    ]

    def runner(role: dict[str, Any]):
        if role["title"] == "A":
            raise RuntimeError("boom")
        return {"processed": role["title"]}

    scheduler = JobScraperScheduler(
        config=config,
        role_runner=runner,
        logger=_make_logger(),
        sleep_fn=lambda _s: None,
    )

    results = scheduler.run_cycle(cycle_num=1)

    statuses = [item["status"] for item in results]
    assert statuses == ["error", "ok"]
    assert results[0]["error"] == "boom"
    assert results[1]["outcome"]["processed"] == "B"


def test_run_forever_respects_max_cycles(monkeypatch):
    """Scheduler stops after max_cycles and honors sleep between cycles."""

    config = Config()
    config.roles = [{"title": "A", "location": "X", "enabled": True}]

    calls: list[str] = []
    sleeps: list[float] = []

    def runner(role: dict[str, Any]):
        calls.append(role["title"])
        return {"processed": role["title"]}

    scheduler = JobScraperScheduler(
        config=config,
        role_runner=runner,
        poll_interval_minutes=0.001,
        logger=_make_logger(),
        sleep_fn=lambda s: sleeps.append(s),
    )

    scheduler.run_forever(max_cycles=2)

    assert calls == ["A", "A"]
    # One sleep between two cycles
    assert len(sleeps) == 1
    assert sleeps[0] >= 0
