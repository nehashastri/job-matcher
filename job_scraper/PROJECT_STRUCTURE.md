# Project Structure (Feature-Based)

## Directory Layout

```
job-scraper/
├── src/
│   ├── __init__.py
│   ├── auth/                    # LinkedIn authentication & session
│   │   ├── __init__.py
│   │   ├── linkedin_auth.py     # Login, cookie management
│   │   └── session_manager.py   # Selenium browser instance, retry logic
│   ├── scraping/                # Job scraping from LinkedIn
│   │   ├── __init__.py
│   │   ├── search_builder.py    # URL construction with filters
│   │   ├── job_list_scraper.py  # Left-pane list scraping
│   │   └── job_detail_scraper.py # Right-pane detail scraping
│   ├── filtering/               # Pre-LLM filtering (blocklist, etc.)
│   │   ├── __init__.py
│   │   └── blocklist.py         # Company blocklist matching
│   ├── matching/                # LLM-based filtering & scoring
│   │   ├── __init__.py
│   │   ├── hr_checker.py        # HR/staffing company detection
│   │   ├── sponsorship_filter.py # Visa sponsorship check
│   │   ├── match_scorer.py      # Match scoring vs resume
│   │   └── resume_loader.py     # PDF resume extraction
│   ├── networking/              # People search & connections
│   │   ├── __init__.py
│   │   ├── people_finder.py     # Search "role at company"
│   │   └── connection_requester.py # Send connection requests
│   ├── storage/                 # Data persistence
│   │   ├── __init__.py
│   │   ├── matched_jobs_store.py # CSV/JSON for matched jobs
│   │   └── blocklist_store.py   # Blocklist file I/O
│   ├── notifications/           # Email alerts
│   │   ├── __init__.py
│   │   └── email_notifier.py    # SMTP email sending
│   ├── scheduler/               # Polling loop orchestration
│   │   ├── __init__.py
│   │   └── job_scraper_scheduler.py # Main polling loop
│   ├── config/                  # Configuration management
│   │   ├── __init__.py
│   │   └── config.py            # Load .env, validate config
│   ├── utils/                   # Utilities
│   │   ├── __init__.py
│   │   ├── logger.py            # Daily log rotation, formatting
│   │   ├── helpers.py           # Generic helpers
│   │   └── exceptions.py        # Custom exceptions
│   └── cli/                     # CLI entry point
│       ├── __init__.py
│       └── main.py              # CLI commands
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures, mocks
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_auth/
│   │   │   └── test_linkedin_auth.py
│   │   ├── test_scraping/
│   │   │   ├── test_search_builder.py
│   │   │   └── test_job_scraper.py
│   │   ├── test_filtering/
│   │   │   └── test_blocklist.py
│   │   ├── test_matching/
│   │   │   ├── test_hr_checker.py
│   │   │   ├── test_sponsorship_filter.py
│   │   │   ├── test_match_scorer.py
│   │   │   └── test_resume_loader.py
│   │   ├── test_networking/
│   │   │   └── test_people_finder.py
│   │   ├── test_storage/
│   │   │   ├── test_matched_jobs_store.py
│   │   │   └── test_blocklist_store.py
│   │   ├── test_notifications/
│   │   │   └── test_email_notifier.py
│   │   └── test_config/
│   │       └── test_config.py
│   └── integration/
│       ├── __init__.py
│       ├── test_scraping_to_filtering.py
│       ├── test_matching_pipeline.py
│       ├── test_full_workflow.py
│       └── fixtures/
│           ├── mock_linkedin.py
│           ├── mock_llm.py
│           └── sample_data.py
├── data/
│   ├── roles.json               # User's role definitions (example)
│   ├── company_blocklist.json   # Blocked companies (auto-updated)
│   ├── master_resume.pdf        # User's resume
│   ├── matched_jobs.csv         # Results (generated)
│   ├── matched_jobs.json        # Results (generated)
│   ├── .linkedin_cookies.pkl    # Session cookies (auto-generated)
│   └── logs/                    # Daily log files
│       ├── job_scraper_2025-01-01.log
│       └── job_scraper_2025-01-02.log
├── pixi.toml                    # Pixi configuration
├── pyproject.toml               # Python project metadata
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore (include .env, .pkl, logs)
├── README.md                    # User guide
├── SETUP.md                     # Setup instructions
├── ARCHITECTURE.md              # Architecture & design
├── IMPLEMENTATION_PLAN.md       # (this file)
├── PROJECT_STRUCTURE.md         # (this file)
└── COPILOT.md                   # Agent instructions
```

---

## Module Descriptions

### `src/auth/`
**Responsibility**: Handle LinkedIn login, cookie persistence, and session management.

#### `linkedin_auth.py`
- `class LinkedInAuth`
  - `login(email: str, password: str) -> bool`: login to LinkedIn; save cookies to file
  - `load_cookies() -> bool`: load cookies from file; inject into session
  - `is_logged_in() -> bool`: check if session is valid
  - Methods handle retries with exponential backoff

#### `session_manager.py`
- `class SessionManager`
  - `__init__()`: initialize Selenium WebDriver (Chrome), load/create cookies
  - `get_driver() -> WebDriver`: return active driver
  - `close() -> None`: close driver and cleanup
  - Methods for retry logic, explicit waits, error handling

---

### `src/scraping/`
**Responsibility**: Navigate LinkedIn search results and extract job data.

#### `search_builder.py`
- `class SearchBuilder`
  - `build_url(role: str, location: str, filters: dict) -> str`: construct LinkedIn search URL
  - Methods to add filters (date_posted, experience, remote, f_TPR)
  - Examples:
    ```python
    url = builder.build_url(
        "Software Engineer",
        "New York, NY",
        {"date_posted": "r3600", "experience": ["entry", "associate"], "remote": "hybrid"}
    )
    ```

#### `job_list_scraper.py`
- `class JobListScraper`
  - `scrape_list(driver: WebDriver, url: str) -> list[dict]`: scrape left-pane job list
  - Returns: `[{"job_id": "...", "title": "...", "company": "...", "viewed": false}, ...]`
  - Handles pagination, stale elements, timeouts
  - Filters out viewed jobs automatically

#### `job_detail_scraper.py`
- `class JobDetailScraper`
  - `scrape_detail(driver: WebDriver, job_id: str) -> dict`: click job in list, scrape right-pane
  - Returns: full job dict including description, seniority, remote flag, posted_time, etc.
  - Handles timeouts, retries, element stales

---

### `src/filtering/`
**Responsibility**: Apply pre-LLM filters (company blocklist).

#### `blocklist.py`
- `class Blocklist`
  - `__init__(file_path: str)`: load blocklist from JSON
  - `is_blocked(company: str) -> bool`: check if company is blocked (exact or regex match)
  - `add(company: str) -> None`: add company to blocklist and persist
  - Examples:
    ```python
    blocklist.add("Lensa")  # Exact match
    blocklist.add("*.recruiter.com")  # Regex/pattern
    ```

---

### `src/matching/`
**Responsibility**: LLM-based filtering and job scoring.

#### `hr_checker.py`
- `class HRChecker`
  - `is_hr_company(company: str, description: str = "") -> dict`: call LLM to detect HR firms
  - Returns: `{"is_hr_company": true/false, "reason": "..."}`
  - Handles LLM errors, invalid JSON, retries

#### `sponsorship_filter.py`
- `class SponsorshipFilter`
  - `check(description: str) -> dict`: call LLM to detect no-sponsorship statements
  - Returns: `{"decision": "accept"/"reject", "reason": "..."}`
  - Handles LLM errors, retries

#### `match_scorer.py`
- `class MatchScorer`
  - `score(job_dict: dict, resume_text: str, preferences: str = "") -> dict`: call LLM to score job fit
  - Returns: `{"score": 0-10, "reasoning": "...", "verdict": "accept"/"reject"}`
  - Threshold configurable; default 8
  - Handles LLM errors, invalid JSON, retries

#### `resume_loader.py`
- `class ResumeLoader`
  - `load(file_path: str) -> str`: extract text from PDF via pypdf
  - Returns: plain text resume
  - Handles missing file, corrupt PDF, exceptions

---

### `src/networking/`
**Responsibility**: Search for people in matching roles and send connection requests.

#### `people_finder.py`
- `class PeopleFinder`
  - `search_and_connect(driver: WebDriver, role: str, company: str) -> int`: open new tab, search people, send requests
  - Scrapes first 3 pages (or until exhausted)
  - Returns: count of connection requests sent
  - Handles tab management, navigation, element parsing, rate limits
  - Closes tab and returns to main tab

#### `connection_requester.py`
- `class ConnectionRequester`
  - `send_request(driver: WebDriver, person_url: str) -> bool`: send connection request to one person
  - Max 10 requests per page; 1–2s delay between requests
  - Handles failures gracefully; logs attempts
  - Returns: success/failure

---

### `src/storage/`
**Responsibility**: Persist matched jobs and blocklist.

#### `matched_jobs_store.py`
- `class MatchedJobsStore`
  - `append(job_dict: dict) -> None`: append matched job to CSV and JSON
  - `load_all() -> list[dict]`: load all matched jobs from CSV
  - Columns: job_id, title, company, location, remote, seniority, posted_time, job_url, match_score, matched_at, connections_sent, email_sent
  - Handles file creation, appending, error handling

#### `blocklist_store.py`
- `class BlocklistStore`
  - `load() -> list[str]`: load blocklist from JSON
  - `add(company: str) -> None`: add company and persist
  - Prevents duplicates

---

### `src/notifications/`
**Responsibility**: Send email alerts.

#### `email_notifier.py`
- `class EmailNotifier`
  - `__init__(smtp_config: dict)`: setup SMTP from config
  - `send(job_dict: dict, connections_count: int) -> bool`: compose and send email
  - Subject: "Job Match Alert: {title} at {company}"
  - Body: details, match score, job URL, connection count
  - Handles SMTP errors, retries, logs failures

---

### `src/scheduler/`
**Responsibility**: Main polling loop and orchestration.

#### `job_scraper_scheduler.py`
- `class JobScraperScheduler`
  - `__init__(config: dict, session_manager, logger)`: init with config, components, logger
  - `run() -> None`: main loop; cycle through roles every 30 minutes
  - `run_once() -> None`: single cycle (for testing)
  - For each role:
    1. Build URL
    2. Scrape list
    3. For each unviewed job:
       - Scrape details
       - Apply blocklist
       - Check HR (if enabled)
       - Check sponsorship (if enabled)
       - Score match (if not rejected)
       - If accepted:
         - Store to CSV/JSON
         - People search in new tab
         - Send email
    4. Log cycle end
  - Handles errors, retries, graceful shutdown

---

### `src/config/`
**Responsibility**: Load and validate configuration.

#### `config.py`
- `class Config`
  - `load_env()`: load .env file
  - `validate()`: check required vars (email, password, API key)
  - `get(key: str) -> Any`: retrieve config value
  - Provides defaults for optional vars

---

### `src/utils/`
**Responsibility**: Utilities and helpers.

#### `logger.py`
- `class JobScraperLogger`
  - `__init__(log_dir: str)`: initialize daily log rotation
  - `log(level: str, category: str, message: str)`: log with timestamp and format
  - Auto-rotates at 00:00; creates new file per date
  - Formats: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [CATEGORY] message`
  - Supports both file and console output

#### `helpers.py`
- Utility functions: `sleep_with_jitter(min: int, max: int)`, `extract_domain(url: str)`, etc.

#### `exceptions.py`
- Custom exceptions: `LinkedInAuthError`, `ScrapingError`, `LLMError`, etc.

---

### `src/cli/`
**Responsibility**: Command-line interface.

#### `main.py`
- `def main()`: entry point
- Commands (via click):
  - `scrape`: run single polling cycle
  - `loop`: run continuous loop (default 30 min interval)
  - `show-jobs`: display matched jobs
  - Options: `--interval MINUTES`, `--config PATH`

---

## Data Files

### `data/roles.json` (Example)
```json
[
  {
    "role": "Software Engineer",
    "location": "New York, NY",
    "date_posted": "r3600",
    "experience_levels": ["entry", "associate"],
    "remote": "hybrid",
    "requires_sponsorship": true,
    "accept_hr_companies": false
  },
  {
    "role": "Product Manager",
    "location": "San Francisco, CA",
    "date_posted": "past_week",
    "experience_levels": ["mid-senior"],
    "remote": "remote",
    "requires_sponsorship": false,
    "accept_hr_companies": true
  }
]
```

### `data/company_blocklist.json` (Example)
```json
{
  "companies": [
    "Lensa",
    "Staffing Inc",
    "*.temp-agency.com"
  ]
}
```

### `data/matched_jobs.csv` (Generated)
```
job_id,title,company,location,remote,seniority,posted_time,job_url,match_score,matched_at,connections_sent,email_sent
12345,Software Engineer,Acme Corp,New York NY,hybrid,Mid-Senior,2025-01-01T10:30:00Z,https://linkedin.com/jobs/...,8.5,2025-01-01T11:45:00Z,12,true
```

### `data/matched_jobs.json` (Generated)
```json
{
  "jobs": [
    {
      "job_id": "12345",
      "title": "Software Engineer",
      "company": "Acme Corp",
      "location": "New York, NY",
      "remote": "hybrid",
      "seniority": "Mid-Senior",
      "posted_time": "2025-01-01T10:30:00Z",
      "job_url": "https://linkedin.com/jobs/...",
      "match_score": 8.5,
      "matched_at": "2025-01-01T11:45:00Z",
      "connections_sent": 12,
      "email_sent": true
    }
  ]
}
```

---

## Testing Structure

### Unit Tests (`tests/unit/`)
- Test individual modules in isolation (mock external dependencies)
- Examples:
  - `test_search_builder.py`: test URL construction with various filters
  - `test_blocklist.py`: test company matching (exact & regex)
  - `test_match_scorer.py`: test LLM response parsing
  - `test_resume_loader.py`: test PDF extraction

### Integration Tests (`tests/integration/`)
- Test component interactions (some mocking, some real components)
- Examples:
  - `test_scraping_to_filtering.py`: scrape → blocklist filter
  - `test_matching_pipeline.py`: HR check → sponsorship → scoring
  - `test_full_workflow.py`: login → scrape → filter → match → store → notify

### Fixtures (`tests/conftest.py` & `tests/integration/fixtures/`)
- Mock LinkedIn responses, LLM calls, SMTP
- Sample job data, resumes, config

---

## Key Design Decisions

1. **Feature-based structure**: Each feature (auth, scraping, matching, etc.) is a separate module for clarity and testability.
2. **Separation of concerns**: auth, scraping, filtering, and notification are independent.
3. **LLM abstraction**: HR check, sponsorship, and scoring are isolated LLM calls for easy customization.
4. **Error handling**: Every module has retry logic and graceful degradation (log and continue).
5. **Logging**: Centralized logger with daily rotation and structured format.
6. **Configuration**: Single source of truth (`.env` + `roles.json`) loaded at startup.
7. **Storage**: CSV for human-readability, JSON for flexibility; both updated on each match.
