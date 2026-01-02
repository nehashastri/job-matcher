# LinkedIn Job Scraper

Automation that logs into LinkedIn, scrapes roles, filters them with rules and LLM checks, scores fit against your resume, and alerts you when a good match is found. Designed to run locally without an orchestrator service.

## What it does
- Scrape LinkedIn search results (left-pane lists and right-pane details) with Selenium + Chrome.
- Apply company blocklist and HR-company detection; optionally reject roles that do not sponsor visas.
- Score matches with OpenAI models against your resume; configurable rerank on a stronger model.
- Persist accepted jobs to Excel and send email notifications; optionally collect people to connect with.

## Core workflow (Phases 1–7)
- Auth/session: [auth/linkedin_auth.py](auth/linkedin_auth.py) and [auth/session_manager.py](auth/session_manager.py).
- Search URL builder: [scraping/search_builder.py](scraping/search_builder.py).
- Scraping: [scraping/job_list_scraper.py](scraping/job_list_scraper.py) (JobSummary) and [scraping/job_detail_scraper.py](scraping/job_detail_scraper.py) (JobDetails).
- Filtering: [filtering/blocklist.py](filtering/blocklist.py) and [matching/hr_checker.py](matching/hr_checker.py).
- Sponsorship: [matching/sponsorship_filter.py](matching/sponsorship_filter.py).
- Matching: [matching/resume_loader.py](matching/resume_loader.py) and [matching/match_scorer.py](matching/match_scorer.py).
- Networking: [networking/people_finder.py](networking/people_finder.py) and [networking/connection_requester.py](networking/connection_requester.py).
- Notifications: [notifications/email_notifier.py](notifications/email_notifier.py).
- Storage: [storage_pkg/matched_jobs_store.py](storage_pkg/matched_jobs_store.py) and [storage_pkg/blocklist_store.py](storage_pkg/blocklist_store.py).

## Key files and folders
- [app/job_finder.py](app/job_finder.py): CLI entry that wires scraping, scoring, storage, and notifications (no external orchestrator).
- [scraping/linkedin_scraper.py](scraping/linkedin_scraper.py): LinkedIn-specific end-to-end scraper.
- [models.py](models.py): Domain dataclasses (JobSummary, JobDetails, ProfileCard).
- [project_config/pixi.toml](project_config/pixi.toml) and [project_config/pyproject.toml](project_config/pyproject.toml): tooling and dependency setup.
- [data/](data): runtime inputs/outputs (roles.json, company_blocklist.json, jobs.xlsx, linkedin_connections.xlsx).

## Run
```powershell
cd "d:\Projects\Job List\job_scraper"
pixi -C project_config install
Copy-Item project_config/.env.template .env

# Single scrape over configured roles
pixi -C project_config run scrape

# Continuous loop (interval from .env)
pixi -C project_config run loop
```

Place your resume at data/resume.docx and update data/roles.json plus data/company_blocklist.json before running.

## Configuration
- Environment: set values in .env (OpenAI keys, LinkedIn creds, email SMTP, thresholds, polling interval).
- Chrome profile: set CHROME_PROFILE_PATH (or remote debugging port) if you want to reuse an existing session.
- Sponsorship/HR: toggle REQUIRES_SPONSORSHIP and REJECT_HR_COMPANIES flags in .env/config.
- Match scoring: OPENAI_MODEL, OPENAI_MODEL_RERANK, JOB_MATCH_THRESHOLD, JOB_MATCH_RERANK_BAND.

## Outputs
- [data/jobs.xlsx](data/jobs.xlsx) for accepted jobs.
- [data/linkedin_connections.xlsx](data/linkedin_connections.xlsx) for networking records.
- [data/company_blocklist.json](data/company_blocklist.json) and [data/roles.json](data/roles.json) for inputs.
- [logs/job_finder.log](logs/job_finder.log) (created at runtime).

## Testing
```powershell
pixi -C project_config run test
# or
pixi run python -m pytest
```

## Troubleshooting
- Chrome session: verify CHROME_PROFILE_PATH or remote debugging flags; ensure Chrome is closed when copying profiles.
- Login failures: recheck LINKEDIN_EMAIL/LINKEDIN_PASSWORD; solve any CAPTCHA manually.
- OpenAI errors: confirm OPENAI_API_KEY, model names, and network access.
- Empty results: relax filters in data/roles.json or lower JOB_MATCH_THRESHOLD.
