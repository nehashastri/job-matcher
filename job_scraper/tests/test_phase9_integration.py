"""
Phase 9 integration tests: validate orchestrated workflow with mocked pipeline
components (scraper, LLM scoring, email) and scheduler coordination.
"""

import logging
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("openpyxl")

from config.config import Config
from scheduler.job_scraper_scheduler import JobScraperScheduler
from storage_pkg import MatchedJobsStore

# Helpers --------------------------------------------------------------


def _null_logger() -> logging.Logger:
    logger = logging.getLogger("test.phase9")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def _fake_role_runner_factory(
    data_dir: Path,
    email_calls: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    connections: list[dict[str, Any]],
):
    """Build a role runner that mimics the scrape→score→store→email path."""

    store = MatchedJobsStore(data_dir=str(data_dir))

    def runner(role: dict[str, Any]) -> dict[str, Any]:
        accepted = []
        for job in jobs:
            threshold = job.get("threshold", 8)
            if job.get("match_score", 0) < threshold:
                continue

            role_tag = role.get("title", "")
            job_for_role = {
                **job,
                # Give each role a unique ID suffix so pagination/tests can assert per-role saves
                "id": f"{job.get('id', '')}-{role_tag}",
            }

            store.add_job(job_for_role)
            for conn in connections:
                store.add_linkedin_connection(
                    {
                        **conn,
                        "company": job.get("company", ""),
                        "role": job.get("title", ""),
                    }
                )
            accepted.append(job_for_role)

        email_calls.append(
            {
                "role": role.get("title", ""),
                "accepted": len(accepted),
            }
        )

        return {
            "role": role.get("title", ""),
            "location": role.get("location", ""),
            "jobs_seen": len(jobs),
            "accepted": len(accepted),
        }

    return runner, store


# Tests ----------------------------------------------------------------


def test_full_workflow_stores_jobs_connections_and_emails(tmp_path: Path):
    jobs = [
        {
            "id": "123",
            "title": "Senior Python Developer",
            "company": "Tech Corp",
            "location": "Remote",
            "url": "https://example.com/jobs/123",
            "source": "LinkedIn",
            "applicant_count": 42,
            "posted_date": "2026-01-01",
            "match_score": 9.2,
            "threshold": 8.0,
        },
        {
            "id": "999",
            "title": "Junior Developer",
            "company": "Tech Corp",
            "location": "Remote",
            "url": "https://example.com/jobs/999",
            "source": "LinkedIn",
            "applicant_count": 10,
            "posted_date": "2026-01-02",
            "match_score": 6.0,
            "threshold": 8.0,
        },
    ]

    connections = [
        {
            "name": "Alex Lead",
            "title": "Engineering Manager",
            "url": "https://www.linkedin.com/in/alex",
            "company": "",
            "country": "United States",
            "role_match": True,
            "message_available": True,
            "connected": True,
            "status": "Connected",
        },
        {
            "name": "Casey PM",
            "title": "Product Manager",
            "url": "https://www.linkedin.com/in/casey",
            "company": "",
            "country": "United States",
            "role_match": False,
            "message_available": False,
            "connected": False,
            "status": "Pending",
        },
    ]

    email_calls: list[dict[str, Any]] = []

    config = Config()
    config.roles = [
        {"title": "Backend", "location": "Remote", "enabled": True},
    ]

    role_runner, store = _fake_role_runner_factory(
        data_dir=tmp_path,
        email_calls=email_calls,
        jobs=jobs,
        connections=connections,
    )

    scheduler = JobScraperScheduler(
        config=config,
        role_runner=role_runner,
        poll_interval_minutes=0.001,
        logger=_null_logger(),
        sleep_fn=lambda _s: None,
    )

    results = scheduler.run_cycle(cycle_num=1)

    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["outcome"]["accepted"] == 1
    assert email_calls == [{"role": "Backend", "accepted": 1}]

    stored_jobs = store.get_all_jobs()
    assert len(stored_jobs) == 1
    assert stored_jobs[0]["Title"] == "Senior Python Developer"
    assert stored_jobs[0]["Company"] == "Tech Corp"
    assert stored_jobs[0]["Match Score"] == 9.2

    stored_connections = store.get_all_connections()
    assert len(stored_connections) == 2
    assert stored_connections[0]["Role Match"] == "Yes"
    assert stored_connections[1]["Role Match"] == "No"


def test_scheduler_continues_after_role_error(tmp_path: Path):
    config = Config()
    config.roles = [
        {"title": "Fail", "location": "X", "enabled": True},
        {"title": "Ok", "location": "Y", "enabled": True},
    ]

    calls: list[str] = []

    def runner(role: dict[str, Any]):
        calls.append(role["title"])
        if role["title"] == "Fail":
            raise RuntimeError("boom")
        # No-op pipeline for the second role
        return {"accepted": 0, "jobs_seen": 0}

    scheduler = JobScraperScheduler(
        config=config,
        role_runner=runner,
        logger=_null_logger(),
        sleep_fn=lambda _s: None,
    )

    results = scheduler.run_cycle(cycle_num=5)

    assert calls == ["Fail", "Ok"]
    statuses = [item["status"] for item in results]
    assert statuses == ["error", "ok"]
    assert results[0]["error"] == "boom"


def test_multiple_roles_happy_path(tmp_path: Path):
    jobs = [
        {
            "id": "777",
            "title": "Data Engineer",
            "company": "DataWorks",
            "location": "NYC",
            "url": "https://example.com/jobs/777",
            "source": "LinkedIn",
            "applicant_count": 12,
            "posted_date": "2026-01-01",
            "match_score": 8.5,
            "threshold": 8.0,
        }
    ]

    email_calls: list[dict[str, Any]] = []

    config = Config()
    config.roles = [
        {"title": "RoleA", "location": "NYC", "enabled": True},
        {"title": "RoleB", "location": "SF", "enabled": True},
    ]

    role_runner, store = _fake_role_runner_factory(
        data_dir=tmp_path,
        email_calls=email_calls,
        jobs=jobs,
        connections=[],
    )

    scheduler = JobScraperScheduler(
        config=config,
        role_runner=role_runner,
        poll_interval_minutes=0.001,
        logger=_null_logger(),
        sleep_fn=lambda _s: None,
    )

    results = scheduler.run_cycle(cycle_num=2)

    assert [r["status"] for r in results] == ["ok", "ok"]
    assert [call["role"] for call in email_calls] == ["RoleA", "RoleB"]

    jobs_saved = store.get_all_jobs()
    assert len(jobs_saved) == 2
    assert all(job["Title"] == "Data Engineer" for job in jobs_saved)
