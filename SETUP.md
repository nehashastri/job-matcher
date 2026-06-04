# Setup Guide for Job Scraper

This guide provides step-by-step instructions to clone, configure, and run the Job Scraper project. It also explains how to customize prompts and settings for your workflow.
---

## 1. Prerequisites
- Python 3.10+
- Google Chrome (for Selenium)
- Git
- OpenAI API key for LLM features
## 2. Clone the Repository
```sh
git clone <your-repo-url>
cd job_scraper
```

## 3. Install Dependencies (Pixi Only)
```powershell
pixi install
```

## 4. Configure Environment Variables
Create a `.env` file in the root directory and set:
```
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_email_password
EMAIL_FROM=your_email@example.com
EMAIL_TO=recipient@example.com
ENABLE_EMAIL_NOTIFICATIONS=True
```

## 5. Modify Prompts (Optional)
- Edit prompt templates in `data/LLM_base_score.txt`, `data/LLM_rerank_score.txt` to customize LLM behavior.

## 6. Configure Roles and Blocklist
- Edit `data/roles.json` to define job search roles (title, location, experience, etc.).
- Update `data/company_blocklist.json` to block unwanted companies.

## 7. Run the Scraper
- CLI entry point:
```powershell
pixi run scrape         # Scrape jobs once
pixi run loop           # Run continuous scheduler loop
pixi run show-jobs      # Show jobs from the last 24 hours
pixi run stats          # Show job statistics
## 8. Turn On/Off Features
- In `config/config.py` or your `.env`, adjust settings:
    - `ENABLE_EMAIL_NOTIFICATIONS`: Enable/disable email alerts
    - `SCRAPE_INTERVAL_MINUTES`: Set polling interval
    - `REJECT_HR_COMPANIES`: Block HR/staffing firms
    - `JOB_MATCH_THRESHOLD`: Set match score threshold
    - `MAX_APPLICANTS`: Limit number of jobs per scrape
    - `HEADLESS`: Run browser in headless mode

## 9. Logs and Output
- Scraped jobs: `data/jobs.csv`
- Logs: `logs/` directory
- Notifications: Email and/or desktop (Windows)

## 10. Testing
- Run all tests:
    ```powershell
    pixi run test
- Run with coverage:
    ```powershell
    pixi run test-cov

## 11. Troubleshooting
- Check logs for errors
- Ensure all environment variables are set
- Verify Chrome and Python versions
- For LLM errors, check OpenAI API key and prompt files

---

For advanced configuration, see comments in `config/config.py` and each module's docstring.
# Setup Guide for Job Scraper

This guide provides step-by-step instructions to clone, configure, and run the Job Scraper project. It also explains how to customize prompts and settings for your workflow.

---

## 1. Prerequisites
- Python 3.10+
- Google Chrome (for Selenium)
- Git
- OpenAI API key for LLM features

## 2. Clone the Repository
```sh
git clone <your-repo-url>
cd job_scraper
```

## 3. Install Dependencies
- Recommended: Use a virtual environment
```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
- If using `pixi.toml` or `pyproject.toml`, follow project-specific instructions:
```sh
pip install -e .
```

## 4. Configure Environment Variables
Create a `.env` file in the root directory and set:
```
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_email_password
EMAIL_FROM=your_email@example.com
EMAIL_TO=recipient@example.com
ENABLE_EMAIL_NOTIFICATIONS=True
```

## 5. Modify Prompts (Optional)
- Edit prompt templates in `data/LLM_base_score.txt`, `data/LLM_rerank_score.txt` to customize LLM behavior.

## 6. Configure Roles and Blocklist
- Edit `data/roles.json` to define job search roles (title, location, experience, etc.).
- Update `data/company_blocklist.json` to block unwanted companies.

## 7. Run the Scraper
- CLI entry point:
```sh
python -m cli.main
```
- Or run the scheduler directly:
```sh
python scheduler/job_scraper_scheduler.py
```

## 8. Turn On/Off Features
- In `config/config.py` or your `.env`, adjust settings:
    - `ENABLE_EMAIL_NOTIFICATIONS`: Enable/disable email alerts
    - `SCRAPE_INTERVAL_MINUTES`: Set polling interval
    - `REJECT_HR_COMPANIES`: Block HR/staffing firms
    - `JOB_MATCH_THRESHOLD`: Set match score threshold
    - `MAX_APPLICANTS`: Limit number of jobs per scrape
    - `HEADLESS`: Run browser in headless mode

## 9. Logs and Output
- Scraped jobs: `data/jobs.csv`
- Logs: `logs/` directory
- Notifications: Email and/or desktop (Windows)

## 10. Troubleshooting
- Check logs for errors
- Ensure all environment variables are set
- Verify Chrome and Python versions
- For LLM errors, check OpenAI API key and prompt files

---

For advanced configuration, see comments in `config/config.py` and each module's docstring.
