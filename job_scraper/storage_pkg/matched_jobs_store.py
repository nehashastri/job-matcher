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
    """
    Store and manage jobs/contacts in CSV format.

    Attributes:
        data_dir (Path): Directory where CSV files are stored.
        jobs_csv (Path): Path to jobs.csv file.
    """

    def __init__(self, data_dir: str | Path | None = None):
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        """
        Initialize MatchedJobsStore.

        Args:
            data_dir (str | Path | None): Directory to store CSV files. Defaults to DATA_DIR.
        """
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(exist_ok=True)
        self.jobs_csv = self.data_dir / "jobs.csv"
        self.connections_csv = self.data_dir / "linkedin_connections.csv"
        self._init_jobs_file()
        self._init_connections_file()

    # ---------- Initialization ----------
    def _init_jobs_file(self) -> None:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._init_jobs_file")
        """
        Ensure jobs CSV file exists. Creates an empty file if not present.
        """
        if not self.jobs_csv.exists():
            self._write_jobs_csv([])

    def _init_connections_file(self) -> None:
        logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._init_connections_file"
        )
        """
        Ensure linkedin_connections.csv file exists. Creates an empty file if not present.
        """
        if not self.connections_csv.exists():
            self._write_connections_csv([])

    def add_people_profiles(
        self, profiles: list[dict[str, Any]], searched_job_title: str = ""
    ) -> bool:
        logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}.add_people_profiles"
        )
        """
        Add people profiles to linkedin_connections.csv. Each profile should include name, title, profile_url, company.
        Args:
            profiles (list[dict[str, Any]]): List of people profile dicts.
            searched_job_title (str): The job title used for searching (optional, for context).
        Returns:
            bool: True if writing succeeds, False otherwise.
        """
        # Prepare rows for CSV
        rows = []
        for profile in profiles:
            rows.append(
                {
                    "Name": profile.get("name", ""),
                    "Title": profile.get("title", ""),
                    "URL": profile.get("profile_url", ""),
                    "Company": profile.get("company", ""),
                    "Searched Job Title": searched_job_title,
                }
            )
        return self._write_connections_csv(rows)

    def _write_connections_csv(self, profiles: list[dict[str, Any]]) -> bool:
        logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._write_connections_csv"
        )
        """
        Write the list of people profiles to linkedin_connections.csv using CONNECTION_HEADERS.
        Args:
            profiles (list[dict[str, Any]]): List of profile dicts to write.
        Returns:
            bool: True if writing succeeds, False otherwise.
        """
        from utils.csv_utils import write_dicts_to_csv

        return write_dicts_to_csv(
            self.connections_csv, CONNECTION_HEADERS, profiles, logger
        )

    # ---------- Jobs ----------
    def add_job(self, job: dict[str, Any]) -> bool:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.add_job")
        """
        Append a job to jobs.csv. Does not update existing jobs.

        Args:
            job (dict[str, Any]): Job dictionary with required fields.

        Returns:
            bool: True if job added successfully, False otherwise.
        """
        try:
            title = job.get("title") or job.get("Title", "")
            company = job.get("company") or job.get("Company", "")
            url = job.get("url") or job.get("URL", "")
            applicants = job.get("applicant_count") or job.get("Applicants", 0)
            match_score = job.get("match_score") or job.get("Match Score", 0)

            row = {
                "Title": title,
                "Company": company,
                "URL": url,
                "Applicants": applicants,
                "Match Score": match_score,
            }

            # Append to CSV
            file_exists = self.jobs_csv.exists()
            with open(self.jobs_csv, "a", encoding="utf-8", newline="") as f:
                import csv

                fieldnames = ["Title", "Company", "URL", "Applicants", "Match Score"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists or f.tell() == 0:
                    writer.writeheader()
                writer.writerow(row)
            logger.info(f"Added job: {title} at {company}")
            return True
        except Exception as exc:
            logger.error(f"Error adding job: {exc}")
            return False

    def get_all_jobs(self) -> list[dict[str, Any]]:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.get_all_jobs")
        """
        Read all jobs from jobs.csv and return as a list of dictionaries.

        Returns:
            list[dict[str, Any]]: List of job dictionaries.
        """
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
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._write_jobs_csv")
        """
        Write the list of jobs to jobs.csv using the provided fieldnames.

        Args:
            jobs (list[dict[str, Any]]): List of job dictionaries to write.

        Returns:
            bool: True if writing succeeds, False otherwise.
        """
        from utils.csv_utils import write_dicts_to_csv

        fieldnames = ["Title", "Company", "URL", "Applicants", "Match Score"]
        return write_dicts_to_csv(self.jobs_csv, fieldnames, jobs, logger)

    # Only CSV logic remains.

    def get_stats(self) -> dict[str, Any]:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.get_stats")
        """
        Get statistics about the jobs stored (e.g., total job count).

        Returns:
            dict[str, Any]: Dictionary with job statistics.
        """
        jobs = self.get_all_jobs()
        return {"total_jobs": len(jobs)}
