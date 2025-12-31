# Setup

## Prerequisites

- **Windows 10/11**
- **Chrome browser** installed
- **Pixi** package manager ([install guide](https://pixi.sh))
- **OpenAI API key** ([get one here](https://platform.openai.com/api-keys))
- **LinkedIn account** with login credentials

## Quick Start

1. **Clone the repository:**
   ```powershell
   git clone <repository-url>
   cd job-scraper
   ```

2. **Install dependencies:**
   ```powershell
   pixi install
   ```

3. **Create `.env` file:**
   ```powershell
   copy .env.example .env
   ```

4. **Edit `.env` with your credentials:**
   ```bash
   # Required
   OPENAI_API_KEY=sk-proj-...        # Get from OpenAI dashboard
   LINKEDIN_EMAIL=you@example.com
   LINKEDIN_PASSWORD=your_password

   # Optional (defaults shown)
   OPENAI_MODEL=gpt-4o-mini
   JOB_MATCH_THRESHOLD=8
   SCRAPE_INTERVAL_MINUTES=30
   ```

5. **Add your resume:**
   - Place your resume PDF in `data/resume.pdf`
   - The scraper uses this for LLM matching

6. **Add job preferences (optional):**
   - Create `data/preferences.txt`
   - Add one preference per line, for example:
     ```
     Remote work options
     Python development
     Machine learning projects
     Startup environment
     ```

7. **Run the scraper:**
   ```powershell
   # Single scrape
   pixi run scrape

   # Continuous loop (checks every 30 minutes by default)
   pixi run loop

   # View saved jobs
   pixi run show-jobs
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for LLM matching |
| `LINKEDIN_EMAIL` | Yes | - | LinkedIn account email |
| `LINKEDIN_PASSWORD` | Yes | - | LinkedIn account password |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model to use |
| `JOB_MATCH_THRESHOLD` | No | `8` | Minimum match score (0-10) |
| `SCRAPE_INTERVAL_MINUTES` | No | `30` | Loop interval in minutes |

### Job Preferences

The `data/preferences.txt` file is optional but recommended. Add specific requirements to help the LLM match better:

```
Python development
Remote-first company
Health insurance
401k matching
Work-life balance
```

## Output Files

After running the scraper, check these files:

- **`data/jobs.csv`** - Matched jobs with all details (CSV format)
- **`data/jobs.xlsx`** - Matched jobs with formatting (Excel format)
- **`data/linkedin_connections.csv`** - People found at matched companies
- **`data/linkedin_connections.xlsx`** - Excel version with formatting
- **`data/viewed_jobs.json`** - Tracks viewed jobs to avoid duplicates
- **`logs/job_finder.log`** - Application logs for debugging

## Troubleshooting

### Common Issues

**"Chrome driver not found"**
- Selenium 4.15+ auto-manages ChromeDriver
- Ensure Chrome browser is installed

**"LinkedIn login failed"**
- Verify credentials in `.env` file
- LinkedIn may show CAPTCHA (solve manually if needed)
- Check for rate limiting

**"OpenAI API error"**
- Verify API key is correct
- Check API quota and billing
- Ensure network connectivity

**"No jobs found"**
- Filters may be too restrictive
- Try lowering `JOB_MATCH_THRESHOLD`
- Check LinkedIn has recent jobs matching criteria

**"Windows notification not showing"**
- Ensure notifications are enabled in Windows settings
- Package `win10toast` must be installed

### Getting Help

1. Check logs in `logs/job_finder.log`
2. Review error messages in console output
3. Verify all prerequisites are installed
4. Check `.env` file has all required values

## Next Steps

After setup:
1. Run a test scrape: `pixi run scrape`
2. Check `data/jobs.xlsx` for results
3. Adjust `JOB_MATCH_THRESHOLD` in `.env` if needed
4. Set up continuous loop: `pixi run loop`

For development and architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).

For AI agent instructions, see [COPILOT.md](COPILOT.md).
