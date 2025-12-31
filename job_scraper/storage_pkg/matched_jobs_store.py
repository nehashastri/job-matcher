"""
Job storage implementation (CSV/Excel).
Mirrors legacy storage.py functionality for matched jobs and connections.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class MatchedJobsStore:
    """Store and manage jobs in CSV/Excel format"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.jobs_file = self.data_dir / "jobs.csv"
        self.jobs_excel = self.data_dir / "jobs.xlsx"
        self.connections_file = self.data_dir / "linkedin_connections.csv"
        self.connections_excel = self.data_dir / "linkedin_connections.xlsx"

        # Initialize files if they don't exist
        self._init_files()

    def _init_files(self):
        """Initialize CSV files with headers"""
        if not self.jobs_file.exists():
            with open(self.jobs_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "ID",
                        "Title",
                        "Company",
                        "Location",
                        "Job URL",
                        "Source",
                        "Applicants",
                        "Posted Date",
                        "Scraped Date",
                        "Match Score",
                        "Viewed",
                        "Saved",
                        "Applied",
                        "Emailed",
                    ]
                )

        if not self.connections_file.exists():
            with open(self.connections_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Date",
                        "Name",
                        "Title",
                        "LinkedIn URL",
                        "Role Searched",
                        "Country",
                        "Message Sent",
                        "Status",
                    ]
                )

    def add_job(self, job: dict[str, Any]) -> bool:
        """Add or update a job in CSV"""
        try:
            existing_jobs = self.get_all_jobs()
            job_id = job.get("id", hash(job.get("url")))

            # Update existing
            for i, existing in enumerate(existing_jobs):
                if existing.get("ID") == str(job_id):
                    existing_jobs[i].update(
                        {
                            "Title": job.get("title", ""),
                            "Company": job.get("company", ""),
                            "Location": job.get("location", ""),
                            "Job URL": job.get("url", ""),
                            "Source": job.get("source", ""),
                            "Applicants": job.get("applicant_count", 0),
                        }
                    )
                    self._write_jobs_csv(existing_jobs)
                    return True

            # Add new job
            job_row = {
                "ID": str(job_id),
                "Title": job.get("title", ""),
                "Company": job.get("company", ""),
                "Location": job.get("location", ""),
                "Job URL": job.get("url", ""),
                "Source": job.get("source", ""),
                "Applicants": job.get("applicant_count", 0),
                "Posted Date": job.get("posted_date", ""),
                "Scraped Date": datetime.now().isoformat(),
                "Match Score": job.get("match_score", 0),
                "Viewed": "No",
                "Saved": "No",
                "Applied": "No",
                "Emailed": "No",
            }

            existing_jobs.append(job_row)
            self._write_jobs_csv(existing_jobs)

            logger.info(f"Added job: {job.get('title')} at {job.get('company')}")
            return True
        except Exception as e:
            logger.error(f"Error adding job: {str(e)}")
            return False

    def get_all_jobs(self) -> list[dict[str, Any]]:
        """Get all jobs from CSV"""
        try:
            if not self.jobs_file.exists():
                return []

            with open(self.jobs_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader) if reader else []
        except Exception as e:
            logger.error(f"Error reading jobs: {str(e)}")
            return []

    def _write_jobs_csv(self, jobs: list[dict[str, Any]]):
        """Write jobs to CSV"""
        with open(self.jobs_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "ID",
                "Title",
                "Company",
                "Location",
                "Job URL",
                "Source",
                "Applicants",
                "Posted Date",
                "Scraped Date",
                "Match Score",
                "Viewed",
                "Saved",
                "Applied",
                "Emailed",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(jobs)

    def export_to_excel(self, jobs: list[dict[str, Any]] | None = None) -> bool:
        """Export jobs to Excel with formatting"""
        if not EXCEL_AVAILABLE:
            logger.warning("openpyxl not installed. Install with: pip install openpyxl")
            return False

        try:
            if jobs is None:
                jobs = self.get_all_jobs()

            if not jobs:
                logger.warning("No jobs to export")
                return False

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Jobs"

            headers = [
                "ID",
                "Title",
                "Company",
                "Location",
                "Job URL",
                "Source",
                "Applicants",
                "Posted Date",
                "Scraped Date",
                "Match Score",
                "Viewed",
                "Saved",
                "Applied",
                "Emailed",
            ]
            ws.append(headers)

            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")

            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for job in jobs:
                ws.append(
                    [
                        job.get("ID", ""),
                        job.get("Title", ""),
                        job.get("Company", ""),
                        job.get("Location", ""),
                        job.get("Job URL", ""),
                        job.get("Source", ""),
                        job.get("Applicants", ""),
                        job.get("Posted Date", ""),
                        job.get("Scraped Date", ""),
                        job.get("Match Score", ""),
                        job.get("Viewed", ""),
                        job.get("Saved", ""),
                        job.get("Applied", ""),
                        job.get("Emailed", ""),
                    ]
                )

            widths = {
                "A": 10,
                "B": 30,
                "C": 20,
                "D": 15,
                "E": 40,
                "F": 12,
                "G": 12,
                "H": 15,
                "I": 15,
                "J": 12,
                "K": 10,
                "L": 10,
                "M": 10,
                "N": 10,
            }

            for col, width in widths.items():
                ws.column_dimensions[col].width = width

            for row in range(2, len(jobs) + 2):
                url_cell = ws[f"E{row}"]
                if url_cell.value:
                    url_cell.hyperlink = url_cell.value
                    url_cell.font = Font(color="0563C1", underline="single")

            wb.save(self.jobs_excel)
            logger.info(f"Exported {len(jobs)} jobs to {self.jobs_excel}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to Excel: {str(e)}")
            return False

    # ---- Connections handling ----
    def add_linkedin_connection(self, connection: dict[str, Any]) -> bool:
        """Record a LinkedIn connection attempt"""
        try:
            connections = self.get_all_connections()

            connection_row = {
                "Date": datetime.now().isoformat(),
                "Name": connection.get("name", ""),
                "Title": connection.get("title", ""),
                "LinkedIn URL": connection.get("url", ""),
                "Role Searched": connection.get("role", ""),
                "Country": connection.get("country", ""),
                "Message Sent": connection.get("message_sent", "Yes"),
                "Status": connection.get("status", "Sent"),
            }

            connections.append(connection_row)
            self._write_connections_csv(connections)

            logger.info(f"Recorded connection to {connection.get('name')}")
            return True

        except Exception as e:
            logger.error(f"Error adding connection: {str(e)}")
            return False

    def get_all_connections(self) -> list[dict[str, Any]]:
        """Get all LinkedIn connections from CSV"""
        try:
            if not self.connections_file.exists():
                return []

            with open(self.connections_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader) if reader else []
        except Exception as e:
            logger.error(f"Error reading connections: {str(e)}")
            return []

    def _write_connections_csv(self, connections: list[dict[str, Any]]):
        """Write connections to CSV"""
        with open(self.connections_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "Date",
                "Name",
                "Title",
                "LinkedIn URL",
                "Role Searched",
                "Country",
                "Message Sent",
                "Status",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(connections)

    def export_connections_to_excel(self, connections: list[dict[str, Any]] | None = None) -> bool:
        """Export LinkedIn connections to Excel"""
        if not EXCEL_AVAILABLE:
            logger.warning("openpyxl not installed. Install with: pip install openpyxl")
            return False

        try:
            if connections is None:
                connections = self.get_all_connections()

            if not connections:
                logger.warning("No connections to export")
                return False

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "LinkedIn Connections"

            headers = [
                "Date",
                "Name",
                "Title",
                "LinkedIn URL",
                "Role Searched",
                "Country",
                "Message Sent",
                "Status",
            ]
            ws.append(headers)

            header_fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")

            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for conn in connections:
                ws.append(
                    [
                        conn.get("Date", ""),
                        conn.get("Name", ""),
                        conn.get("Title", ""),
                        conn.get("LinkedIn URL", ""),
                        conn.get("Role Searched", ""),
                        conn.get("Country", ""),
                        conn.get("Message Sent", ""),
                        conn.get("Status", ""),
                    ]
                )

            widths = {"A": 20, "B": 20, "C": 30, "D": 40, "E": 20, "F": 12, "G": 15, "H": 12}

            for col, width in widths.items():
                ws.column_dimensions[col].width = width

            for row in range(2, len(connections) + 2):
                url_cell = ws[f"D{row}"]
                if url_cell.value:
                    url_cell.hyperlink = url_cell.value
                    url_cell.font = Font(color="0563C1", underline="single")

            wb.save(self.connections_excel)
            logger.info(f"Exported {len(connections)} connections to {self.connections_excel}")
            return True

        except Exception as e:
            logger.error(f"Error exporting connections: {str(e)}")
            return False

    # ---- Misc helpers ----
    def mark_job_status(self, job_id: str, status: str, value: bool = True):
        """Update job status (viewed, saved, applied, emailed)"""
        try:
            jobs = self.get_all_jobs()

            for job in jobs:
                if job.get("ID") == str(job_id):
                    job[status] = "Yes" if value else "No"
                    break

            self._write_jobs_csv(jobs)
            return True
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Basic stats for CLI display."""
        jobs = self.get_all_jobs()
        return {
            "total_jobs": len(jobs),
        }
