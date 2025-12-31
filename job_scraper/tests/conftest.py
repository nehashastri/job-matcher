"""
Test fixtures and utilities for job scraper tests
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables"""
    env_vars = {
        "OPENAI_API_KEY": "test-api-key",
        "OPENAI_MODEL": "gpt-4o-mini",
        "JOB_MATCH_THRESHOLD": "8",
        "LINKEDIN_EMAIL": "test@example.com",
        "LINKEDIN_PASSWORD": "test_password",
        "RESUME_PATH": "./data/resume.pdf",
        "ROLES_PATH": "./data/roles.json",
        "BLOCKLIST_PATH": "./data/company_blocklist.json",
        "SCRAPE_INTERVAL_MINUTES": "30",
        "MAX_RETRIES": "5",
        "REQUEST_DELAY_MIN": "2",
        "REQUEST_DELAY_MAX": "5",
        "MAX_JOBS_PER_ROLE": "50",
        "MAX_APPLICANTS": "100",
        "REQUIRES_SPONSORSHIP": "true",
        "SKIP_VIEWED_JOBS": "true",
        "LOG_LEVEL": "INFO",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_roles_json(temp_dir):
    """Create a mock roles.json file"""
    roles_data = {
        "roles": [
            {
                "title": "Software Engineer",
                "location": "United States",
                "experience_levels": ["Entry level"],
                "remote": True,
                "keywords": ["python"],
                "enabled": True,
            },
            {
                "title": "Data Engineer",
                "location": "United States",
                "experience_levels": ["Entry level"],
                "remote": True,
                "keywords": ["ETL"],
                "enabled": False,
            },
        ],
        "search_settings": {
            "date_posted": "r86400",
            "applicant_limit": 100,
            "requires_sponsorship": True,
        },
    }

    roles_path = temp_dir / "roles.json"
    with open(roles_path, "w", encoding="utf-8") as f:
        json.dump(roles_data, f)

    return roles_path


@pytest.fixture
def mock_blocklist_json(temp_dir):
    """Create a mock company_blocklist.json file"""
    blocklist_data = {
        "blocklist": ["Lensa", "Dice", "Jobot"],
        "patterns": [".*[Rr]ecruiting.*", ".*[Ss]taffing.*"],
        "notes": "Test blocklist",
    }

    blocklist_path = temp_dir / "company_blocklist.json"
    with open(blocklist_path, "w", encoding="utf-8") as f:
        json.dump(blocklist_data, f)

    return blocklist_path


@pytest.fixture
def mock_resume_file(temp_dir):
    """Create a mock resume PDF file"""
    resume_path = temp_dir / "resume.pdf"
    resume_path.write_text("Mock resume content")
    return resume_path


@pytest.fixture
def mock_preferences_file(temp_dir):
    """Create a mock preferences file"""
    preferences_path = temp_dir / "preferences.txt"
    preferences_path.write_text("Looking for Python backend roles\nRemote work preferred")
    return preferences_path
