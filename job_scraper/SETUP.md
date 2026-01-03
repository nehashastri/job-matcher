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
# Browser mode
HEADLESS=false  # set to true in CI or when you don't need a visible Chrome window
```

3) Provide inputs

# Reject unpaid/volunteer roles and cap experience
REJECT_UNPAID_ROLES=true
REJECT_VOLUNTEER_ROLES=true
MIN_REQUIRED_EXPERIENCE_YEARS=0
ALLOW_PHD_REQUIRED=true
## Optional: Gmail app password
1) Enable 2FA on your Google account.
2) Generate an App Password (Google Account > Security > App passwords) for Mail/Custom name.
3) Place the 16-character password (no spaces) in SMTP_PASSWORD.
4) Set ENABLE_EMAIL_NOTIFICATIONS=true to send alerts.

## Resume tips
- Use .docx (not .pdf) so python-docx can extract text.
## Run
```powershell
# Single pass over configured roles
cd "D:\Projects\Job List\job_scraper\project_config"
pixi run scrape

# (Equivalent from repo root)
cd "D:\Projects\Job List\job_scraper"
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
- Chrome/driver: ensure Chrome is installed.
- Login: verify LinkedIn credentials and handle any CAPTCHA prompts manually.
- OpenAI: check OPENAI_API_KEY and model names; ensure network egress is allowed.
- Empty results: loosen filters in data/roles.json or lower JOB_MATCH_THRESHOLD.
