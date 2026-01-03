# LinkedIn Job Scraper

Automation that logs into LinkedIn, scrapes roles, filters them with rules and LLM checks, scores fit against your resume, and alerts you when a good match is found. Designed to run locally without an orchestrator service.

## What you can configure
- Toggle sponsorship and HR filters: `REQUIRES_SPONSORSHIP`, `REJECT_HR_COMPANIES`.
- Control scraping scope: `MAX_JOBS_PER_ROLE`, `MAX_APPLICANTS`, `SCRAPE_INTERVAL_MINUTES`, `HEADLESS` mode.
- Tune scoring: `JOB_MATCH_THRESHOLD`, `JOB_MATCH_RERANK_BAND`, `OPENAI_MODEL`, `OPENAI_MODEL_RERANK`.
- Data inputs: `data/roles.json` for roles, `data/company_blocklist.json` for blocked companies, `data/resume.docx` for your resume (all gitignored; use the *.example files as templates).

## How it works
1) Sign in and keep the session alive. The scraper logs in (headless or visible Chrome) and reuses the session while it runs.
2) Build LinkedIn search URLs per role. It applies your filters (location, date posted, experience, remote, sponsorship flag) and opens the results.
3) Paginate and load job cards. For each page it scrolls until the list is full (25 cards on non-final pages), waits for loaders to finish, and dedupes cards by `data-job-id`.
4) Skip already viewed cards. Anything marked as viewed is ignored when `SKIP_VIEWED_JOBS` is true.
5) Open each new job and scrape details. The right pane is scraped for title, company, location, applicants, posting date, description, and the canonical job URL.
6) Filter companies. Blocklisted names/patterns are dropped. An HR/staffing detector (LLM) can reject staffing firms when enabled.
7) Filter for sponsorship. If `REQUIRES_SPONSORSHIP` is true, a sponsorship LLM check rejects roles that say “no sponsorship” or “US only”.
8) Score the fit. The resume text is compared to the job description with an LLM. Scores ≥ threshold are kept (optionally reranked with a stronger model near the threshold).
9) Store accepted jobs. Accepted roles are written to `data/jobs.xlsx` with metadata and timestamps.
10) (Optional) Network on LinkedIn People search. For accepted roles, the networking module can search people at the company and log connection attempts in `data/linkedin_connections.xlsx`.
11) Notify you. An email can be sent via Gmail SMTP summarizing the job and connection counts.
12) Repeat for the next page and the next role on the schedule.

## Directory layout
```
job_scraper/
├── app/                     # entry points (main CLI in job_finder.py)
├── auth/                    # LinkedIn login + session management
├── cli/                     # legacy CLI glue
├── config/                  # config loader, logging setup
├── data/                    # gitignored user data/outputs; *.example templates here
├── filtering/               # blocklist utilities
├── matching/                # HR checker, sponsorship filter, resume loader, match scorer
├── networking/              # people finder and connection requester
├── notifications/           # email notifier
├── scraping/                # search builder, list/detail scrapers, LinkedIn orchestrator
├── scheduler/               # polling loop orchestration
├── storage_pkg/             # Excel-backed stores for jobs and connections
├── tests/                   # unit and integration tests
├── project_config/          # tooling (pixi.toml, pyproject.toml, .env.template)
├── logs/                    # runtime logs (gitignored)
├── README.md                # this guide
├── SETUP.md                 # setup steps
├── ARCHITECTURE.md          # architecture notes
├── IMPLEMENTATION_PLAN.md   # phased build plan
├── PROJECT_STRUCTURE.md     # module overview
├── COPILOT.md               # agent instructions
└── .github/workflows/ci.yml # CI (lint + tests)
```


