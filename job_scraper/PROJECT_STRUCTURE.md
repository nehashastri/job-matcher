# Project Structure

## Directory Layout (current)

```
job_scraper/
├── app/                     # Runtime entry points
│   ├── job_finder.py        # Main CLI app (uses scraping + matching + storage)
│   └── storage.py           # Storage shim for Excel exports
├── auth/                    # LinkedIn authentication & browser session
├── cli/                     # CLI wiring (legacy)
├── config/                  # Config loader + logging helpers
├── filtering/               # Blocklist and related filters
├── matching/                # HR checker, sponsorship filter, match scoring, resume loader
├── networking/              # People finder + connection requests
├── notifications/           # Email notifier
├── scraping/                # Search builder, list/detail scrapers, LinkedIn scraper
├── scheduler/               # Job scraper scheduler shell
├── storage_pkg/             # Blocklist/matched job persistence
├── data/                    # User/working data (roles.json, company_blocklist.json, etc.)
├── scripts/                 # Manual runbooks and debug helpers
│   ├── debug_scraper.py
│   ├── test_linkedin_login.py
│   ├── test_phase2_manual.py
│   ├── test_quick.py
│   ├── test_viewed_detection.py
│   ├── test_viewed_jobs.py
│   └── test_viewed_results.txt
├── project_config/          # Tooling/config files (pixi.toml, pyproject.toml, .env.template)
├── tests/                   # Automated tests (unit/integration)
├── logs/                    # Runtime logs (gitignored)
├── COPILOT.md               # Agent instructions (kept at root)
├── ARCHITECTURE.md          # Architecture notes
├── IMPLEMENTATION_PLAN.md   # Phase plan
├── PROJECT_STRUCTURE.md     # (this file)
├── README.md                # User guide
├── SETUP.md                 # Setup guide
└── (no duplicate doc copies; use root docs)
```

## Key Modules (by folder)

- `auth/`: `linkedin_auth.py`, `session_manager.py` for login + Selenium driver lifecycle.
- `scraping/`: `search_builder.py`, `job_list_scraper.py`, `job_detail_scraper.py`, `linkedin_scraper.py` for LinkedIn list/detail scraping.
- `filtering/`: `blocklist.py` for company filtering.
- `matching/`: `hr_checker.py`, `sponsorship_filter.py`, `match_scorer.py`, `resume_loader.py` for LLM-based checks.
- `networking/`: `people_finder.py`, `connection_requester.py` for connection workflows.
- `storage_pkg/`: `blocklist_store.py`, `matched_jobs_store.py` for persistence.
- `notifications/`: `email_notifier.py` for SMTP alerts.
- `app/job_finder.py`: main CLI that wires scraping + matching + storage + notifications.
- `scripts/`: manual/debug scripts; run them via Pixi, e.g., `pixi -C project_config run python ../scripts/test_quick.py`.

## Config & Tooling

- All tooling/config files live in `project_config/` (`pixi.toml`, `pyproject.toml`, `.env.template`).
- Place your real `.env` at the repo root (gitignored). Use the template in `project_config/.env.template` as a reference.

## Data & Logs

- `data/roles.json`, `data/company_blocklist.json`, `data/jobs.xlsx`, `data/linkedin_connections.xlsx`, etc. hold user/config data (CSV files are legacy and migrated on first run).
- `logs/` is for runtime logs; it is gitignored and may be created at runtime.

## Docs

- Canonical docs live at the repo root: `README.md`, `SETUP.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `PROJECT_STRUCTURE.md`, `COPILOT.md`.
- Removed legacy `docs/` copies to avoid duplication.
- Examples:
  - `test_search_builder.py`: test URL construction with various filters
  - `test_blocklist.py`: test company matching (exact & regex)
  - `test_match_scorer.py`: test LLM response parsing
  - `test_resume_loader.py`: test Word document extraction

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
7. **Storage**: Excel (.xlsx) for human-readability; kept in `data/jobs.xlsx` and `data/linkedin_connections.xlsx`.
