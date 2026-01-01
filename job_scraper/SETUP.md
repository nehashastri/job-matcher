# Setup

## Prerequisites
- Windows 10/11
- Chrome installed
- Pixi package manager (https://pixi.sh)
- OpenAI API key
- LinkedIn credentials

## Install
```powershell
cd "d:\Projects\Job List\job_scraper"
pixi -C project_config install
```

## Configure
1. Create your env file
   ```powershell
   Copy-Item project_config/.env.template .env
   ```
2. Fill required keys (minimum)
   ```
   OPENAI_API_KEY=sk-...
   LINKEDIN_EMAIL=you@example.com
   LINKEDIN_PASSWORD=your_password
   OPENAI_MODEL=gpt-4o-mini
   MATCH_SCORE_THRESHOLD=8
   POLL_INTERVAL_MINUTES=30
   ```
3. Provide inputs
   - `data/master_resume.docx` (your resume)
   - `data/roles.json` (roles + locations + filters)
   - `data/company_blocklist.json` (optional blocklist)

## Run
```powershell
# Single pass over configured roles
pixi -C project_config run scrape

# Continuous polling (interval from .env)
pixi -C project_config run loop
```

## Outputs
- `data/jobs.csv` and `data/jobs.xlsx` for accepted jobs
- `data/linkedin_connections.csv` and `data/linkedin_connections.xlsx` for saved contacts
- `data/company_blocklist.json` and `data/roles.json` for inputs
- `logs/job_finder.log` (daily rotated) for execution logs

## Testing
- Using pixi task: `pixi -C project_config run test`
- Or directly: `pixi run python -m pytest`

## Troubleshooting
- Chrome/driver: ensure Chrome is installed; Selenium manages the driver.
- Login failures: recheck creds; solve any CAPTCHA manually.
- OpenAI errors: verify API key, quota, and network.
- Empty results: relax filters in `data/roles.json` or lower `MATCH_SCORE_THRESHOLD`.

## Related docs
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Implementation and test plan: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Project map: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
