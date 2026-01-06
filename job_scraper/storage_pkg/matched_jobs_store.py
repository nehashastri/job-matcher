"""Job and contact storage backed by CSV (.csv)."""

import csv
import logging
from pathlib import Path
from typing import Any

from config.config import DATA_DIR

logger = logging.getLogger(__name__)

JOBS_HEADERS = [
    "ID",
    "Title",
    "Company",
    "URL",
    "Match Score",
]

CONNECTION_HEADERS = [
    "Name",
    "Title",
    "URL",
    "Company",
    "Searched Job Title",
]


class MatchedJobsStore:
    """Store and manage jobs/contacts in CSV format."""

    def __init__(self, data_dir: str | Path | None = None):
        # Default to repo-level data directory when not provided
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(exist_ok=True)

        self.jobs_csv = self.data_dir / "jobs.csv"

        self._init_jobs_file()

    # ---------- Initialization ----------
    def _init_jobs_file(self) -> None:
        """Ensure jobs CSV file exists."""
        if not self.jobs_csv.exists():
            self._write_jobs_csv([])

    # ---------- Jobs ----------
    def add_job(self, job: dict[str, Any]) -> bool:
        """Add or update a job in CSV."""
        try:
            jobs = self.get_all_jobs()
            job_id = str(
                job.get("id")
                or job.get("ID")
                or hash(job.get("url") or job.get("Job URL"))
            )

            title = job.get("title") or job.get("Title", "")
            company = job.get("company") or job.get("Company", "")
            url = job.get("url") or job.get("URL", "")
            applicants = job.get("applicant_count") or job.get("Applicants", 0)
            match_score = job.get("match_score") or job.get("Match Score", 0)

            # Update if present
            for existing in jobs:
                if existing.get("ID") == job_id:
                    existing.update(
                        {
                            "Title": title,
                            "Company": company,
                            "URL": url,
                            "Applicants": applicants,
                            "Match Score": match_score,
                        }
                    )
                    self._write_jobs_csv(jobs)
                    return True

            jobs.append(
                {
                    "Title": title,
                    "Company": company,
                    "URL": url,
                    "Applicants": applicants,
                    "Match Score": match_score,
                }
            )
            self._write_jobs_csv(jobs)
            logger.info(f"Added job: {job.get('title')} at {job.get('company')}")
            return True
        except Exception as exc:
            logger.error(f"Error adding job: {exc}")
            return False

    def get_all_jobs(self) -> list[dict[str, Any]]:
        """Read all jobs from CSV."""
        if not self.jobs_csv.exists():
            return []
        try:
            with open(self.jobs_csv, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                return [row for row in reader]
        except Exception as exc:
            logger.error(f"Error reading jobs.csv: {exc}")
            return []

    def _write_jobs_csv(self, jobs: list[dict[str, Any]]) -> bool:
        from utils.csv_utils import write_dicts_to_csv

        fieldnames = ["Title", "Company", "URL", "Applicants", "Match Score"]
        return write_dicts_to_csv(self.jobs_csv, fieldnames, jobs, logger)

    # Only CSV logic remains.

    def get_stats(self) -> dict[str, Any]:
        jobs = self.get_all_jobs()
        return {"total_jobs": len(jobs)}
