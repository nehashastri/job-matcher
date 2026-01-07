# LinkedIn Job Scraper

Automation for finding LinkedIn roles, filtering, LLM-based matching against your resume, and notifying when a good match appears.

## What it does
- Scrape LinkedIn search results for configured roles and locations (Selenium, Chrome).
- Skip already viewed jobs and apply company blocklist/HR-company rejection.
- Optional sponsorship filter and LLM match scoring with configurable threshold.
- Persist accepted jobs to Excel (.xlsx) and send email alerts.
- (Future) People search + connection requests after a job is accepted.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for phased delivery.

## Requirements
- Windows 10/11, Chrome installed
- Pixi (uses `project_config/pixi.toml`)
- OpenAI API key
- LinkedIn credentials

## Quick start
```powershell
cd "d:\Projects\Job List\job_scraper"
pixi -C project_config install
Copy-Item project_config/.env.template .env
```

Fill `.env` (template lists all keys):
```
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini               # first-pass scoring model
OPENAI_MODEL_RERANK=gpt-4o             # stronger model for second-pass rerank (optional)
JOB_MATCH_THRESHOLD=8                  # accept when score >= threshold
JOB_MATCH_RERANK_TRIGGER=8             # rerank only when first-pass score meets/exceeds this trigger
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=your_pw
POLL_INTERVAL_MINUTES=30
```

Place your resume at `data/resume.docx` (full text used; no truncation) and adjust `data/roles.json` + `data/company_blocklist.json` as needed.

## Run
```powershell
# Single scrape for configured roles
pixi -C project_config run scrape

# Continuous loop (polling interval from .env)
pixi -C project_config run loop
```

## Outputs
- data/jobs.xlsx for accepted jobs
- data/linkedin_connections.xlsx for saved contacts
- data/company_blocklist.json and data/roles.json for inputs
- logs/job_finder.log (daily rotated) for execution logs
- Rerank config: `OPENAI_MODEL_RERANK` and `JOB_MATCH_RERANK_BAND` control second-pass scoring cost/accuracy

## Project map
- Code: see [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the folder layout.
- Setup details: [SETUP.md](SETUP.md).
- Test plan: phases and scenarios live in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Testing
Run the automated suite after installing dependencies:
```powershell
# Using pixi task
pixi -C project_config run test

# Or directly
pixi run python -m pytest
```

## Links
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Implementation plan & tests: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Agent notes: [COPILOT.md](COPILOT.md)
