"""
Configuration management for job scraper
Loads settings from .env and provides typed access to configuration values
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables (prefer .env values over existing env vars)
load_dotenv(override=True)

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Ensure required folders exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


class Config:
    """Configuration manager for job scraper"""

    def __init__(self):
        self._load_env_config()
        self._load_json_config()

    def _resolve_path(self, env_var: str, default: Path) -> Path:
        """Resolve a path from env; treat relative values as repo-root relative."""
        value = os.getenv(env_var)
        if not value:
            return default

        candidate = Path(value)
        if candidate.is_absolute():
            return candidate

        return (BASE_DIR / candidate).resolve()

    def _load_env_config(self):
        """Load configuration from environment variables"""
        # OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        # Small/fast model for first-pass scoring
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        # Larger model for rerank/second-pass; defaults to "gpt-4o" when unset
        self.openai_model_rerank = os.getenv("OPENAI_MODEL_RERANK", "gpt-4o")
        # First-pass score at or above this value triggers rerank with a bigger model
        self.job_match_rerank_trigger = float(
            os.getenv("JOB_MATCH_RERANK_TRIGGER", "8")
        )
        # Score band around threshold that triggers rerank with larger model
        self.job_match_rerank_band = float(os.getenv("JOB_MATCH_RERANK_BAND", "1"))
        self.job_match_threshold = float(os.getenv("JOB_MATCH_THRESHOLD", "8"))

        # LinkedIn
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL", "")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD", "")

        # File paths (resolve against repo data dir by default)
        self.resume_path = self._resolve_path("RESUME_PATH", DATA_DIR / "resume.docx")
        self.roles_path = self._resolve_path("ROLES_PATH", DATA_DIR / "roles.json")
        self.blocklist_path = self._resolve_path(
            "BLOCKLIST_PATH", DATA_DIR / "company_blocklist.json"
        )

        # Scraping settings
        self.scrape_interval_minutes = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "5"))
        self.request_delay_min = float(os.getenv("REQUEST_DELAY_MIN", "2"))
        self.request_delay_max = float(os.getenv("REQUEST_DELAY_MAX", "5"))
        self.max_jobs_per_role = int(os.getenv("MAX_JOBS_PER_ROLE", "50"))
        self.headless = os.getenv("HEADLESS", "false").lower() == "true"

        # Filtering settings
        self.max_applicants = int(os.getenv("MAX_APPLICANTS", "100"))
        self.requires_sponsorship = (
            os.getenv("REQUIRES_SPONSORSHIP", "true").lower() == "true"
        )
        self.reject_unpaid_roles = (
            os.getenv("REJECT_UNPAID_ROLES", "true").lower() == "true"
        )
        self.reject_volunteer_roles = (
            os.getenv("REJECT_VOLUNTEER_ROLES", "true").lower() == "true"
        )
        self.min_required_experience_years = int(
            os.getenv("MIN_REQUIRED_EXPERIENCE_YEARS", "0")
        )
        self.allow_phd_required = (
            os.getenv("ALLOW_PHD_REQUIRED", "true").lower() == "true"
        )
        self.skip_viewed_jobs = os.getenv("SKIP_VIEWED_JOBS", "true").lower() == "true"
        self.reject_hr_companies = (
            os.getenv("REJECT_HR_COMPANIES", "true").lower() == "true"
        )

        # Networking settings
        self.max_connections_per_job = int(os.getenv("MAX_CONNECTIONS_PER_JOB", "30"))
        self.max_people_search_pages = int(os.getenv("MAX_PEOPLE_SEARCH_PAGES", "3"))
        self.networking_allow_new_tab = (
            os.getenv("NETWORKING_ALLOW_NEW_TAB", "true").lower() == "true"
        )

        # Logging settings
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv(
            "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.log_file_retention_days = int(os.getenv("LOG_FILE_RETENTION_DAYS", "30"))

        # Notification settings
        self.smtp_server = os.getenv("SMTP_SERVER", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.email_from = os.getenv("EMAIL_FROM", "")
        self.email_to = os.getenv("EMAIL_TO", "")
        self.smtp_use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
        self.enable_email_notifications = (
            os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "true").lower() == "true"
        )
        self.enable_toast_notifications = (
            os.getenv("ENABLE_TOAST_NOTIFICATIONS", "true").lower() == "true"
        )

    def _load_json_config(self):
        """Load configuration from JSON files"""
        # Load roles
        self.roles = []
        if self.roles_path.exists():
            try:
                with open(self.roles_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.roles = data.get("roles", [])
                    self.search_settings = data.get("search_settings", {})
            except Exception as e:
                print(f"Warning: Failed to load roles.json: {e}")
                self.search_settings = {}

        # Load blocklist
        self.blocklist = []
        self.blocklist_patterns = []
        if self.blocklist_path.exists():
            try:
                with open(self.blocklist_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.blocklist = data.get("blocklist", [])
                    self.blocklist_patterns = data.get("patterns", [])
            except Exception as e:
                print(f"Warning: Failed to load company_blocklist.json: {e}")

    def validate(self) -> list[str]:
        """
        Validate required configuration values

        Returns:
                List of validation error messages (empty if valid)
        """
        errors = []

        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")

        if not self.linkedin_email:
            errors.append("LINKEDIN_EMAIL is required")

        if not self.linkedin_password:
            errors.append("LINKEDIN_PASSWORD is required")

        if not self.resume_path.exists():
            errors.append(f"Resume file not found: {self.resume_path}")

        if self.job_match_threshold < 0 or self.job_match_threshold > 10:
            errors.append("JOB_MATCH_THRESHOLD must be between 0 and 10")

        if not self.roles:
            errors.append("No roles configured in roles.json")

        return errors

    def get_enabled_roles(self) -> list[dict[str, Any]]:
        """Get list of enabled roles"""
        return [role for role in self.roles if role.get("enabled", True)]

    def add_to_blocklist(self, company: str) -> bool:
        """
        Add a company to the blocklist and save to file

        Args:
                company: Company name to add

        Returns:
                True if successfully added, False otherwise
        """
        if company in self.blocklist:
            return False

        self.blocklist.append(company)

        try:
            # Load current data
            data: dict[str, list[str]] = {"blocklist": [], "patterns": []}
            if self.blocklist_path.exists():
                with open(self.blocklist_path, encoding="utf-8") as f:
                    data = json.load(f)

            # Add company and save
            if company not in data.get("blocklist", []):
                data["blocklist"] = sorted(
                    list(set(data.get("blocklist", []) + [company]))
                )
                with open(self.blocklist_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return True
        except Exception as e:
            print(f"Warning: Failed to update blocklist: {e}")

        return False


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from files"""
    global _config
    _config = Config()
    return _config


# Legacy compatibility - maintain old constants
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30"))
