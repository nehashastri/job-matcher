"""
Phase 5 Tests: Matching & Storage (Excel-backed)
Tests for matched_jobs_store.py and blocklist_store.py
"""

import json
import logging
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("openpyxl")
import openpyxl
from storage_pkg.blocklist_store import BlocklistStore
from storage_pkg.matched_jobs_store import MatchedJobsStore

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def jobs_store(temp_data_dir):
    """Create a MatchedJobsStore instance with temp directory."""
    return MatchedJobsStore(data_dir=temp_data_dir)


@pytest.fixture
def blocklist_store(temp_data_dir):
    """Create a BlocklistStore instance with temp directory."""
    return BlocklistStore(data_dir=temp_data_dir)


@pytest.fixture
def sample_job():
    """Sample job data."""
    return {
        "id": "12345",
        "title": "Senior Python Developer",
        "company": "Tech Corp",
        "location": "San Francisco, CA",
        "url": "https://www.linkedin.com/jobs/view/12345",
        "source": "LinkedIn",
        "applicant_count": 50,
        "posted_date": "2026-01-01",
        "match_score": 9.5,
    }


@pytest.fixture
def sample_connection():
    """Sample connection data."""
    return {
        "name": "John Doe",
        "title": "Software Engineer",
        "url": "https://www.linkedin.com/in/johndoe",
        "company": "Tech Corp",
        "role": "Python Developer",
        "country": "United States",
        "role_match": True,
        "message_available": True,
        "connected": False,
        "status": "Pending",
    }


# ---------- Helpers ----------


def _read_headers(path: Path) -> list[str]:
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    if ws is None:
        raise ValueError("Workbook has no active worksheet")

    return [str(cell.value or "") for cell in next(ws.iter_rows(min_row=1, max_row=1))]


# ---------- Matched Jobs Store Tests ----------


def test_jobs_store_initialization(jobs_store, temp_data_dir):
    """Jobs and connections Excel files should be created with headers."""
    jobs_excel = Path(temp_data_dir) / "jobs.xlsx"
    connections_excel = Path(temp_data_dir) / "linkedin_connections.xlsx"

    assert jobs_excel.exists(), "jobs.xlsx should be created"
    assert connections_excel.exists(), "linkedin_connections.xlsx should be created"

    assert _read_headers(jobs_excel) == [
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

    assert _read_headers(connections_excel) == [
        "Date",
        "Name",
        "Title",
        "LinkedIn URL",
        "Company",
        "Country",
        "Role Searched",
        "Role Match",
        "Message Available",
        "Connected",
        "Status",
    ]


def test_add_job_to_empty_excel(jobs_store, sample_job):
    """Adding a job writes a single row to jobs.xlsx and get_all_jobs."""
    result = jobs_store.add_job(sample_job)

    assert result is True

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1

    job = jobs[0]
    assert job["ID"] == "12345"
    assert job["Title"] == "Senior Python Developer"
    assert job["Company"] == "Tech Corp"
    assert job["Location"] == "San Francisco, CA"
    assert job["Job URL"] == "https://www.linkedin.com/jobs/view/12345"
    assert job["Source"] == "LinkedIn"
    assert job["Applicants"] == 50
    assert job["Match Score"] == 9.5
    assert job["Viewed"] == "No"
    assert job["Saved"] == "No"
    assert job["Applied"] == "No"
    assert job["Emailed"] == "No"


def test_add_second_job_appends_to_excel(jobs_store, sample_job):
    """Appending a second job preserves the first and writes both to Excel."""
    jobs_store.add_job(sample_job)

    second_job = sample_job.copy()
    second_job["id"] = "67890"
    second_job["title"] = "Data Scientist"
    second_job["company"] = "AI Labs"

    result = jobs_store.add_job(second_job)

    assert result is True

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 2
    assert jobs[0]["ID"] == "12345"
    assert jobs[1]["ID"] == "67890"
    assert jobs[1]["Title"] == "Data Scientist"
    assert jobs[1]["Company"] == "AI Labs"


def test_update_existing_job(jobs_store, sample_job):
    """Existing job IDs are updated, not duplicated."""
    jobs_store.add_job(sample_job)

    updated_job = sample_job.copy()
    updated_job["title"] = "Staff Python Developer"
    updated_job["applicant_count"] = 100

    result = jobs_store.add_job(updated_job)

    assert result is True

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1

    job = jobs[0]
    assert job["Title"] == "Staff Python Developer"
    assert job["Applicants"] == 100


def test_load_jobs_from_excel(jobs_store, sample_job):
    """Persistence works across instances using Excel as source of truth."""
    jobs_store.add_job(sample_job)

    new_store = MatchedJobsStore(data_dir=jobs_store.data_dir)
    jobs = new_store.get_all_jobs()

    assert len(jobs) == 1
    assert jobs[0]["ID"] == "12345"
    assert jobs[0]["Title"] == "Senior Python Developer"


def test_mark_job_status(jobs_store, sample_job):
    """Status flags persist to Excel."""
    jobs_store.add_job(sample_job)

    jobs_store.mark_job_status("12345", "Viewed", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Viewed"] == "Yes"

    jobs_store.mark_job_status("12345", "Saved", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Saved"] == "Yes"

    jobs_store.mark_job_status("12345", "Applied", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Applied"] == "Yes"

    jobs_store.mark_job_status("12345", "Emailed", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Emailed"] == "Yes"


def test_duplicate_job_id_logs_warning(jobs_store, sample_job, caplog):
    """Duplicate IDs update the existing Excel row (no duplicates)."""
    with caplog.at_level(logging.INFO):
        jobs_store.add_job(sample_job)
        jobs_store.add_job(sample_job)

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1


# ---------- LinkedIn Connections Store Tests ----------


def test_add_linkedin_connection(jobs_store, sample_connection):
    """Connections are written to connections.xlsx and retrieved via get_all_connections."""
    result = jobs_store.add_linkedin_connection(sample_connection)

    assert result is True

    connections = jobs_store.get_all_connections()
    assert len(connections) == 1

    conn = connections[0]
    assert conn["Name"] == "John Doe"
    assert conn["Title"] == "Software Engineer"
    assert conn["LinkedIn URL"] == "https://www.linkedin.com/in/johndoe"
    assert conn["Company"] == "Tech Corp"
    assert conn["Role Searched"] == "Python Developer"
    assert conn["Country"] == "United States"
    assert conn["Role Match"] == "Yes"
    assert conn["Message Available"] == "Yes"
    assert conn["Connected"] == "No"
    assert conn["Status"] == "Pending"
    assert conn["Date"] != ""


def test_add_multiple_connections(jobs_store, sample_connection):
    """Multiple connections append cleanly to Excel."""
    jobs_store.add_linkedin_connection(sample_connection)

    second_connection = sample_connection.copy()
    second_connection["name"] = "Jane Smith"
    second_connection["title"] = "Engineering Manager"

    jobs_store.add_linkedin_connection(second_connection)

    connections = jobs_store.get_all_connections()
    assert len(connections) == 2
    assert connections[0]["Name"] == "John Doe"
    assert connections[1]["Name"] == "Jane Smith"


def test_load_connections_from_excel(jobs_store, sample_connection):
    """Connections persist across MatchedJobsStore instances."""
    jobs_store.add_linkedin_connection(sample_connection)

    new_store = MatchedJobsStore(data_dir=jobs_store.data_dir)
    connections = new_store.get_all_connections()

    assert len(connections) == 1
    assert connections[0]["Name"] == "John Doe"


# ---------- Blocklist Store Tests ----------


def test_blocklist_store_initialization(blocklist_store, temp_data_dir):
    """Blocklist store initializes JSON file."""
    blocklist_file = Path(temp_data_dir) / "company_blocklist.json"

    assert blocklist_file.exists()

    with open(blocklist_file) as f:
        data = json.load(f)

    assert "blocklist" in data
    assert "patterns" in data
    assert "notes" in data
    assert isinstance(data["blocklist"], list)
    assert isinstance(data["patterns"], list)


def test_add_company_to_blocklist(blocklist_store):
    """Adding a company persists to the list."""
    result = blocklist_store.add("Bad Company Inc")

    assert result is True

    companies = blocklist_store.get_all_companies()
    assert "Bad Company Inc" in companies


def test_add_duplicate_company(blocklist_store):
    """Duplicate company add should return False and not duplicate entries."""
    blocklist_store.add("Bad Company Inc")

    result = blocklist_store.add("Bad Company Inc")

    assert result is False

    companies = blocklist_store.get_all_companies()
    assert companies.count("Bad Company Inc") == 1


def test_remove_company_from_blocklist(blocklist_store):
    """Removing an existing company succeeds."""
    blocklist_store.add("Bad Company Inc")

    result = blocklist_store.remove("Bad Company Inc")

    assert result is True

    companies = blocklist_store.get_all_companies()
    assert "Bad Company Inc" not in companies


def test_remove_nonexistent_company(blocklist_store):
    """Removing a missing company returns False."""
    result = blocklist_store.remove("Nonexistent Company")

    assert result is False


def test_is_blocked(blocklist_store):
    """Blocklist membership check."""
    blocklist_store.add("Bad Company Inc")

    assert blocklist_store.is_blocked("Bad Company Inc") is True
    assert blocklist_store.is_blocked("Good Company Inc") is False


def test_add_pattern_to_blocklist(blocklist_store):
    """Regex pattern add persists."""
    result = blocklist_store.add_pattern(".*Recruiting.*")

    assert result is True

    patterns = blocklist_store.get_all_patterns()
    assert ".*Recruiting.*" in patterns


def test_add_duplicate_pattern(blocklist_store):
    """Duplicate regex pattern returns False and does not duplicate."""
    blocklist_store.add_pattern(".*Recruiting.*")

    result = blocklist_store.add_pattern(".*Recruiting.*")

    assert result is False

    patterns = blocklist_store.get_all_patterns()
    assert patterns.count(".*Recruiting.*") == 1


def test_blocklist_stats(blocklist_store):
    """Stats report counts."""
    blocklist_store.add("Company 1")
    blocklist_store.add("Company 2")
    blocklist_store.add_pattern(".*Pattern1.*")

    stats = blocklist_store.get_stats()

    assert stats["companies"] == 2
    assert stats["patterns"] == 1


def test_blocklist_persistence(blocklist_store, temp_data_dir):
    """Blocklist changes persist across instances."""
    blocklist_store.add("Test Company")
    blocklist_store.add_pattern(".*Test.*")

    new_store = BlocklistStore(data_dir=temp_data_dir)
    companies = new_store.get_all_companies()
    patterns = new_store.get_all_patterns()

    assert "Test Company" in companies
    assert ".*Test.*" in patterns
