# Job Scraper

## Introduction

Job Scraper is an automated pipeline for scraping job listings from LinkedIn, filtering and matching them to user profiles, and notifying users of relevant opportunities. It leverages LLMs (OpenAI GPT) for HR/staffing detection, job/resume matching, and networking profile relevance. The workflow is modular, configurable, and designed for extensibility and robust error handling.


## Project Structure & File Explanations

```
job_scraper/
├── app/
│   └── job_finder.py                # Main job finding logic and orchestration
├── auth/
│   ├── linkedin_auth.py             # LinkedIn authentication routines
│   └── session_manager.py           # Session management for scraping
├── cli/
│   └── main.py                      # CLI entry point for running the scheduler
├── config/
│   ├── config.py                    # Configuration loader and settings
│   └── logging_utils.py             # Logging setup and utilities
├── data/
│   ├── company_blocklist.json       # List of companies to block (user-editable)
│   ├── jobs.csv                     # Output CSV of scraped jobs
│   ├── linkedin_connections.csv     # Exported LinkedIn connections
│   ├── LLM_base_score.txt           # Prompt for base job/resume scoring
│   ├── LLM_rerank_score.txt         # Prompt for rerank scoring
│   ├── roles.json                   # Roles to search for (user-editable)
│   ├── .env.example                 # Example environment variable file
├── filtering/
│   └── blocklist.py                 # Blocklist logic for filtering companies
├── logs/                            # Log output directory
├── matching/
│   ├── hr_checker.py                # LLM-based HR/staffing company detection
│   ├── match_scorer.py              # LLM-based job/resume match scoring
│   ├── resume_loader.py             # Resume loading and parsing
│   └── sponsorship_filter.py        # Visa sponsorship filtering
├── networking/
│   └── people_finder.py             # LinkedIn people search and networking
├── notifications/
│   └── email_notifier.py            # Email and desktop notification logic
├── project_config/
│   ├── pixi.toml                    # Pixi environment config (optional)
│   └── pyproject.toml               # Python project config (optional)
├── scheduler/
│   └── job_scraper_scheduler.py     # Main scheduler for polling and workflow
├── scraping/
│   ├── base_scraper.py              # Abstract base for scrapers
│   ├── linkedin_scraper.py          # LinkedIn job scraper implementation
│   └── search_builder.py            # LinkedIn search URL builder
├── storage_pkg/
│   ├── blocklist_store.py           # Persistent blocklist storage
│   └── matched_jobs_store.py        # Persistent matched jobs storage
├── tests/                           # Unit and integration tests
├── utils/
│   ├── csv_utils.py                 # CSV writing utilities
│   ├── model_utils.py               # Model and prompt utilities
│   └── webdriver_utils.py           # Selenium WebDriver helpers
```

## Example Files
- `.env.example`: Example environment variable file for configuration
- `company_blocklist.example.json`: Example blocklist for companies
- `roles.example.json`: Example job roles configuration

## Workflow Pseudocode

1. **Initialize Config & Logging**
2. **Start Scheduler Loop**
    - For each enabled role in `roles.json`:
        a. Scrape jobs from LinkedIn using Selenium
        b. For each job:
            i. Filter out blocklisted companies (HR/staffing detection via LLM)
            ii. Score job/resume match (LLM)
            iii. If match score >= threshold, store job and notify user
        c. Optionally, scrape relevant LinkedIn profiles for networking
3. **Send notifications (email, desktop)**
4. **Log all actions, errors, and decisions**

---

See `setup.md` for installation and usage instructions. 
