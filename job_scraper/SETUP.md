# Setup

Step-by-step setup to run the scraper locally without extra services.

## Prerequisites
- Windows 10/11
- Google Chrome installed
- Pixi package manager (https://pixi.sh)
- OpenAI API key
- LinkedIn credentials

## Install dependencies
```powershell
cd "d:\Projects\Job List\job_scraper"
pixi -C project_config install
```

## Configure environment
1) Create your .env from the template
```powershell
Copy-Item project_config/.env.template .env
```

2) Fill required keys (minimum)
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_MODEL_RERANK=gpt-4o
JOB_MATCH_THRESHOLD=8
JOB_MATCH_RERANK_BAND=1
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=your_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=your-email@gmail.com
ENABLE_EMAIL_NOTIFICATIONS=true
```

3) Provide inputs
- data/resume.docx (your resume; keep as .docx)
- data/roles.json (roles, locations, filters)
- data/company_blocklist.json (optional blocklist entries/patterns)

## Optional: Gmail app password
1) Enable 2FA on your Google account.
2) Generate an App Password (Google Account > Security > App passwords) for Mail/Custom name.
3) Place the 16-character password (no spaces) in SMTP_PASSWORD.
4) Set ENABLE_EMAIL_NOTIFICATIONS=true to send alerts.

## Optional: Chrome profile reuse
Reusing a profile reduces CAPTCHA prompts and speeds up login.
- Find your profile path via chrome://version/ (Profile Path).
- Copy that folder to a safe location (Chrome must be closed).
- Set CHROME_PROFILE_PATH in .env to the copied folder path.
- Alternatively, start Chrome manually with --remote-debugging-port and set CHROME_REMOTE_DEBUG_PORT.

## Resume tips
- Use .docx (not .pdf) so python-docx can extract text.
- Tables are supported; images are ignored.
- If your resume lives elsewhere, set RESUME_PATH in .env.

## Run
```powershell
# Single pass over configured roles
pixi -C project_config run scrape

# Continuous polling (interval from .env)
pixi -C project_config run loop
```

## Outputs
- data/jobs.xlsx for accepted jobs
- data/linkedin_connections.xlsx for networking records
- data/company_blocklist.json and data/roles.json for inputs
- logs/job_finder.log (created at runtime)

## Testing
```powershell
pixi -C project_config run test
# or
pixi run python -m pytest
```

## Troubleshooting
- Chrome/driver: ensure Chrome is installed; if profile copy fails, close Chrome and retry.
- Login: verify LinkedIn credentials and CHROME_PROFILE_PATH/remote debugging settings.
- OpenAI: check OPENAI_API_KEY and model names; ensure network egress is allowed.
- Empty results: loosen filters in data/roles.json or lower JOB_MATCH_THRESHOLD.
