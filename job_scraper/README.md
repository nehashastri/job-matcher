# Job Scraper (LinkedIn Only)

Automated LinkedIn job scraper with comprehensive filtering, LLM matching, and Windows notifications.

**Workflow:** Filter LinkedIn jobs (past 24h, Internship/Entry/Associate, US, unviewed, <100 applicants, visa sponsorship) → LLM match ≥8/10 → Find people in similar roles at company → Save to Excel → Windows notification.

## Features
- ✅ **LinkedIn scraping** with Selenium (Chrome required)
- ✅ **Smart filtering:**
  - Posted in past 24 hours
  - Experience level: Internship, Entry, Associate
  - Location: United States
  - Skips already "Viewed" jobs
  - <100 applicants
  - Open to visa sponsorship/international candidates
- ✅ **LLM matching** (OpenAI) against your resume + preferences (≥8/10)
- ✅ **Company people search** - Finds people with similar roles at matched companies (US-based)
- ✅ **Excel export** - Saves jobs and people info to spreadsheet
- ✅ **Windows toast notifications** - No emails, local notifications only
- ✅ **Continuous loop** - Runs all day with custom interval

## Requirements
- Windows 10/11, Python 3.10+, Chrome installed
- OpenAI API key
- LinkedIn credentials

## Quick Start
```powershell
cd "d:\Projects\Job List\job_scraper"
py -3.10 -m venv ..\.venv310
..\.venv310\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env`:
```
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
JOB_MATCH_THRESHOLD=8
RESUME_PATH=./data/resume.pdf
PREFERENCES_PATH=./data/preferences.txt
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=your_pw
```

Place files:
- `data/resume.pdf`
- `data/preferences.txt`

## Commands
```powershell
# Scrape once
python job_finder.py scrape

# Continuous loop (default 30 min intervals)
python job_finder.py loop

# Custom interval (e.g., every 60 minutes)
python job_finder.py loop --interval 60

# Show jobs
python job_finder.py show_jobs
```

## Outputs
- `data/jobs.csv` - All matched jobs with details
- `data/jobs.xlsx` - Excel export of matched jobs
- `data/linkedin_connections.csv` - People found at companies (not connection requests - just saved for reference)
- `logs/job_finder.log` - Full execution log

## 📊 Data Storage

### jobs.csv / jobs.xlsx
Columns: Title, Company, Location, Job URL, Source, Applicants, Posted Date, Scraped Date, Match Score, Viewed, Saved, Applied

### linkedin_connections.csv
Columns: Name, Title, Company, Profile URL, Role, Country, Message Sent, Status

People are saved for reference only - no automatic connection requests sent.

## 📝 Logging

Logs are written to `logs/job_finder.log` with:
- Timestamp for each action
- Log level (INFO, DEBUG, ERROR)
- Component name (scraper.linkedin, etc.)
- Emoji indicators for quick scanning
```powershell
# Real-time tail
Get-Content logs/job_finder.log -Tail 50 -Wait

# Full log
type logs/job_finder.log

# Search logs
Select-String "error" logs/job_finder.log
```

## 🤝 Contributing

To add a new job portal:
1. Create `scrapers/newportal_scraper.py`
2. Extend `BaseScraper`
3. Implement `scrape(max_applicants)` method
4. Add to `JobFinder.scrapers` list
5. Add credentials to `.env.example` if needed

## 📄 License

Private project - personal use only

## ✅ Checklist for Running

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Requirements installed (`pip install -r requirements.txt`)
- [ ] Chrome/Chromium installed (or Selenium Manager auto-downloads)
- [ ] `.env` configured with credentials
- [ ] Gmail app password generated (if using email)
- [ ] Test run completed (`python job_finder.py scrape`)
- [ ] Received test emails (if configured)
- [ ] Excel file created at `data/jobs.xlsx`
