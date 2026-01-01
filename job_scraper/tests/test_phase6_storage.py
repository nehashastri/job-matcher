"""
Phase 6 Tests: Storage & Persistence
Tests for matched_jobs_store.py and blocklist_store.py
"""

import csv
import json
import logging
import tempfile
from pathlib import Path

import pytest
from storage_pkg.blocklist_store import BlocklistStore
from storage_pkg.matched_jobs_store import MatchedJobsStore

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def jobs_store(temp_data_dir):
    """Create a MatchedJobsStore instance with temp directory"""
    return MatchedJobsStore(data_dir=temp_data_dir)


@pytest.fixture
def blocklist_store(temp_data_dir):
    """Create a BlocklistStore instance with temp directory"""
    return BlocklistStore(data_dir=temp_data_dir)


@pytest.fixture
def sample_job():
    """Sample job data"""
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
    """Sample connection data"""
    return {
        "name": "John Doe",
        "title": "Software Engineer",
        "url": "https://www.linkedin.com/in/johndoe",
        "role": "Python Developer",
        "country": "United States",
        "message_sent": "Yes",
        "status": "Pending",
    }


# ========== Matched Jobs Store Tests ==========


def test_jobs_store_initialization(jobs_store, temp_data_dir):
    """Test that jobs store initializes files correctly"""
    jobs_file = Path(temp_data_dir) / "jobs.csv"
    connections_file = Path(temp_data_dir) / "linkedin_connections.csv"

    assert jobs_file.exists(), "jobs.csv should be created"
    assert connections_file.exists(), "linkedin_connections.csv should be created"

    # Check headers
    with open(jobs_file) as f:
        reader = csv.reader(f)
        headers = next(reader)
        assert headers == [
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

    with open(connections_file) as f:
        reader = csv.reader(f)
        headers = next(reader)
        assert headers == [
            "Date",
            "Name",
            "Title",
            "LinkedIn URL",
            "Role Searched",
            "Country",
            "Message Sent",
            "Status",
        ]


def test_add_job_to_empty_csv(jobs_store, sample_job):
    """Test adding a job to an empty CSV"""
    result = jobs_store.add_job(sample_job)

    assert result is True, "add_job should return True"

    # Verify job is in CSV
    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1, "Should have 1 job"

    job = jobs[0]
    assert job["ID"] == "12345"
    assert job["Title"] == "Senior Python Developer"
    assert job["Company"] == "Tech Corp"
    assert job["Location"] == "San Francisco, CA"
    assert job["Job URL"] == "https://www.linkedin.com/jobs/view/12345"
    assert job["Source"] == "LinkedIn"
    assert job["Applicants"] == "50"
    assert job["Match Score"] == "9.5"
    assert job["Viewed"] == "No"
    assert job["Saved"] == "No"
    assert job["Applied"] == "No"
    assert job["Emailed"] == "No"


def test_add_second_job_appends_to_csv(jobs_store, sample_job):
    """Test adding a second job appends correctly"""
    jobs_store.add_job(sample_job)

    second_job = sample_job.copy()
    second_job["id"] = "67890"
    second_job["title"] = "Data Scientist"
    second_job["company"] = "AI Labs"

    result = jobs_store.add_job(second_job)

    assert result is True, "add_job should return True"

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 2, "Should have 2 jobs"

    assert jobs[0]["ID"] == "12345"
    assert jobs[1]["ID"] == "67890"
    assert jobs[1]["Title"] == "Data Scientist"
    assert jobs[1]["Company"] == "AI Labs"


def test_update_existing_job(jobs_store, sample_job):
    """Test updating an existing job by ID"""
    jobs_store.add_job(sample_job)

    # Update the job
    updated_job = sample_job.copy()
    updated_job["title"] = "Staff Python Developer"
    updated_job["applicant_count"] = 100

    result = jobs_store.add_job(updated_job)

    assert result is True, "add_job should return True"

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1, "Should still have 1 job (updated, not duplicated)"

    job = jobs[0]
    assert job["Title"] == "Staff Python Developer"
    assert job["Applicants"] == "100"


def test_load_jobs_from_csv(jobs_store, sample_job):
    """Test loading jobs from CSV maintains data integrity"""
    jobs_store.add_job(sample_job)

    # Create new store instance to force reload from file
    new_store = MatchedJobsStore(data_dir=jobs_store.data_dir)
    jobs = new_store.get_all_jobs()

    assert len(jobs) == 1, "Should load 1 job from CSV"
    assert jobs[0]["ID"] == "12345"
    assert jobs[0]["Title"] == "Senior Python Developer"


def test_mark_job_status(jobs_store, sample_job):
    """Test marking job status (viewed, saved, applied, emailed)"""
    jobs_store.add_job(sample_job)

    # Mark as viewed
    jobs_store.mark_job_status("12345", "Viewed", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Viewed"] == "Yes"

    # Mark as saved
    jobs_store.mark_job_status("12345", "Saved", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Saved"] == "Yes"

    # Mark as applied
    jobs_store.mark_job_status("12345", "Applied", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Applied"] == "Yes"

    # Mark as emailed
    jobs_store.mark_job_status("12345", "Emailed", True)
    jobs = jobs_store.get_all_jobs()
    assert jobs[0]["Emailed"] == "Yes"


def test_duplicate_job_id_logs_warning(jobs_store, sample_job, caplog):
    """Test that duplicate job IDs are handled (updated, not duplicated)"""
    with caplog.at_level(logging.INFO):
        jobs_store.add_job(sample_job)
        jobs_store.add_job(sample_job)  # Add same job again

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1, "Should not create duplicate entries"


# ========== LinkedIn Connections Store Tests ==========


def test_add_linkedin_connection(jobs_store, sample_connection):
    """Test adding a LinkedIn connection"""
    result = jobs_store.add_linkedin_connection(sample_connection)

    assert result is True, "add_linkedin_connection should return True"

    connections = jobs_store.get_all_connections()
    assert len(connections) == 1, "Should have 1 connection"

    conn = connections[0]
    assert conn["Name"] == "John Doe"
    assert conn["Title"] == "Software Engineer"
    assert conn["LinkedIn URL"] == "https://www.linkedin.com/in/johndoe"
    assert conn["Role Searched"] == "Python Developer"
    assert conn["Country"] == "United States"
    assert conn["Message Sent"] == "Yes"
    assert conn["Status"] == "Pending"
    assert "Date" in conn  # Date should be auto-populated


def test_add_multiple_connections(jobs_store, sample_connection):
    """Test adding multiple connections"""
    jobs_store.add_linkedin_connection(sample_connection)

    second_connection = sample_connection.copy()
    second_connection["name"] = "Jane Smith"
    second_connection["title"] = "Engineering Manager"

    jobs_store.add_linkedin_connection(second_connection)

    connections = jobs_store.get_all_connections()
    assert len(connections) == 2, "Should have 2 connections"

    assert connections[0]["Name"] == "John Doe"
    assert connections[1]["Name"] == "Jane Smith"


def test_load_connections_from_csv(jobs_store, sample_connection):
    """Test loading connections from CSV maintains data integrity"""
    jobs_store.add_linkedin_connection(sample_connection)

    # Create new store instance to force reload from file
    new_store = MatchedJobsStore(data_dir=jobs_store.data_dir)
    connections = new_store.get_all_connections()

    assert len(connections) == 1, "Should load 1 connection from CSV"
    assert connections[0]["Name"] == "John Doe"


# ========== Blocklist Store Tests ==========


def test_blocklist_store_initialization(blocklist_store, temp_data_dir):
    """Test that blocklist store initializes correctly"""
    blocklist_file = Path(temp_data_dir) / "company_blocklist.json"

    assert blocklist_file.exists(), "company_blocklist.json should be created"

    with open(blocklist_file) as f:
        data = json.load(f)

    assert "blocklist" in data
    assert "patterns" in data
    assert "notes" in data
    assert isinstance(data["blocklist"], list)
    assert isinstance(data["patterns"], list)


def test_add_company_to_blocklist(blocklist_store):
    """Test adding a company to the blocklist"""
    result = blocklist_store.add("Bad Company Inc")

    assert result is True, "add should return True"

    companies = blocklist_store.get_all_companies()
    assert "Bad Company Inc" in companies


def test_add_duplicate_company(blocklist_store):
    """Test adding duplicate company returns False"""
    blocklist_store.add("Bad Company Inc")

    # Try to add again
    result = blocklist_store.add("Bad Company Inc")

    assert result is False, "add should return False for duplicate"

    companies = blocklist_store.get_all_companies()
    assert companies.count("Bad Company Inc") == 1, "Should only have one entry"


def test_remove_company_from_blocklist(blocklist_store):
    """Test removing a company from the blocklist"""
    blocklist_store.add("Bad Company Inc")

    result = blocklist_store.remove("Bad Company Inc")

    assert result is True, "remove should return True"

    companies = blocklist_store.get_all_companies()
    assert "Bad Company Inc" not in companies


def test_remove_nonexistent_company(blocklist_store):
    """Test removing a company that doesn't exist"""
    result = blocklist_store.remove("Nonexistent Company")

    assert result is False, "remove should return False for nonexistent company"


def test_is_blocked(blocklist_store):
    """Test checking if a company is blocked"""
    blocklist_store.add("Bad Company Inc")

    assert blocklist_store.is_blocked("Bad Company Inc") is True
    assert blocklist_store.is_blocked("Good Company Inc") is False


def test_add_pattern_to_blocklist(blocklist_store):
    """Test adding a regex pattern to the blocklist"""
    result = blocklist_store.add_pattern(".*Recruiting.*")

    assert result is True, "add_pattern should return True"

    patterns = blocklist_store.get_all_patterns()
    assert ".*Recruiting.*" in patterns


def test_add_duplicate_pattern(blocklist_store):
    """Test adding duplicate pattern returns False"""
    blocklist_store.add_pattern(".*Recruiting.*")

    result = blocklist_store.add_pattern(".*Recruiting.*")

    assert result is False, "add_pattern should return False for duplicate"

    patterns = blocklist_store.get_all_patterns()
    assert patterns.count(".*Recruiting.*") == 1


def test_blocklist_stats(blocklist_store):
    """Test getting blocklist statistics"""
    blocklist_store.add("Company 1")
    blocklist_store.add("Company 2")
    blocklist_store.add_pattern(".*Pattern1.*")

    stats = blocklist_store.get_stats()

    assert stats["companies"] == 2
    assert stats["patterns"] == 1


def test_blocklist_persistence(blocklist_store, temp_data_dir):
    """Test that blocklist changes persist across instances"""
    blocklist_store.add("Test Company")
    blocklist_store.add_pattern(".*Test.*")

    # Create new instance to test persistence
    new_store = BlocklistStore(data_dir=temp_data_dir)

    companies = new_store.get_all_companies()
    patterns = new_store.get_all_patterns()

    assert "Test Company" in companies
    assert ".*Test.*" in patterns


# ========== Edge Cases & Error Handling ==========


def test_get_all_jobs_empty(jobs_store):
    """Test getting all jobs when CSV is empty"""
    # Delete all jobs
    jobs_store._write_jobs_csv([])

    jobs = jobs_store.get_all_jobs()
    assert jobs == []


def test_get_all_connections_empty(jobs_store):
    """Test getting all connections when CSV is empty"""
    # Delete all connections
    jobs_store._write_connections_csv([])

    connections = jobs_store.get_all_connections()
    assert connections == []


def test_jobs_stats(jobs_store, sample_job):
    """Test getting job statistics"""
    jobs_store.add_job(sample_job)

    sample_job2 = sample_job.copy()
    sample_job2["id"] = "67890"
    jobs_store.add_job(sample_job2)

    stats = jobs_store.get_stats()

    assert stats["total_jobs"] == 2


def test_empty_blocklist_get_all(blocklist_store):
    """Test getting all companies from empty blocklist"""
    companies = blocklist_store.get_all_companies()
    assert companies == []

    patterns = blocklist_store.get_all_patterns()
    assert patterns == []


def test_job_without_optional_fields(jobs_store):
    """Test adding a job with minimal fields"""
    minimal_job = {
        "id": "minimal-1",
        "title": "Test Job",
        "company": "Test Company",
        "url": "https://example.com/job/1",
    }

    result = jobs_store.add_job(minimal_job)

    assert result is True, "add_job should handle minimal fields"

    jobs = jobs_store.get_all_jobs()
    assert len(jobs) == 1
    assert jobs[0]["ID"] == "minimal-1"
    assert jobs[0]["Location"] == ""  # Should default to empty string
    assert jobs[0]["Applicants"] == "0"  # Should default to 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
