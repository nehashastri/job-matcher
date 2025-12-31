# Architecture

## Goals
- Monitor LinkedIn for user-defined roles (each with a required location) and alert quickly.
- Run locally first; later deploy to cloud for 24/7 coverage.
- Send email alerts as soon as a matching role is found.

## System Overview
- **LinkedIn session**: login, session persistence, cookie reuse, re-login handling.
- **Role & filter config**: roles file (JSON) with required location and optional filters (experience, remote, date posted, requires_sponsorship).
- **Search builder**: construct LinkedIn search URLs, including custom date ranges via `f_TPR`.
- **Scraper**: navigate results, extract job details, respect rate limits; no captcha handling (not expected).
- **List processing**: read left-hand job list, skip entries marked "Viewed", click only unviewed jobs.
- **Detail scraper**: scrape full job details on the right pane for each unviewed job clicked.
- **Company blocklist**: drop roles from blocked companies after scrape (regex/name match).
- **Sponsorship filter (optional)**: if `requires_sponsorship` is true, use LLM to reject roles that say no sponsorship / US citizens only.
- **Matching pipeline**: LLM match scoring (0–10) vs master resume; default accept ≥8/10; prompt customizable.
- **Networking**: after a job is accepted, open new tab, search "role at company", connect with people (≥3 pages), then return to main tab.
- **Notifier**: send email alerts immediately for accepted matches.
- **Scheduler**: continuous polling loop; configurable intervals (default 30 minutes).
- **Logging**: daily log files (rotated at midnight); log every step with timestamps and separators.
- **Persistence**: keep CSV/JSON for matches only; do not store seen jobs (rely on LinkedIn "viewed").
- **Observability**: structured logs, metrics hooks for cloud readiness.

## Configuration Artifacts
- **.env**: credentials and runtime settings
  - `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`
  - Email (Gmail app password): `GMAIL_SMTP_HOST`, `GMAIL_SMTP_PORT`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `ALERT_EMAIL_TO` (recipient)
  - `POLL_INTERVAL_MINUTES` (default 30)
  - `OPENAI_API_KEY` (for LLM calls)
  - `OPENAI_MODEL` (default gpt-4o-mini)
  - `MATCH_SCORE_THRESHOLD` (default 8)
- **Roles file**: `data/roles.json`
  - `role` (e.g., "Software Engineer") — required
  - `location` (e.g., "New York, NY") — required
  - `date_posted` — one of: `any`, `past_month`, `past_week`, `past_24h`, or `r<seconds>` (3600–86400). Default: `r3600` (last hour).
  - `experience_levels` — subset of: `internship`, `entry`, `associate`, `mid-senior`, `director`, `executive`
  - `remote` — one of: `on-site`, `hybrid`, `remote`
  - `requires_sponsorship` — boolean; if true, run sponsorship rejection filter
  - `accept_hr_companies` — boolean (default false); if false, reject roles posted by staffing/HR/recruiter firms and auto-add to blocklist
  - Optional (future): keywords include/exclude, company include/exclude, applicant-count cap
- **Company blocklist file** (JSON, path e.g., `data/company_blocklist.json`): list of company names/patterns to drop after scraping.
- **Master resume** (`data/master_resume.pdf`): user's resume for LLM matching.

## Workflow (Local, then Cloud)
1. Load `.env`; validate required fields.
2. Login to LinkedIn (Selenium); persist cookies to `data/.linkedin_cookies.pkl`; retry on failure with exponential backoff (base 2s, max 30s).
3. Load `data/roles.json` and `data/company_blocklist.json`; validate each role has a location.
4. Load `data/master_resume.pdf`; extract text via pypdf.
5. For each role:
   - Build the LinkedIn search URL with filters.
   - If `date_posted` is `r<number>` and 3600 ≤ number ≤ 86400, set `f_TPR=r<number>`.
   - Apply experience and remote filters when provided.
   - Add random delay (2–5s) before navigating to respect rate limits.
6. Polling loop (default every 30 minutes):
   - Open search URL, paginate results.
   - From the left-hand list, read all jobs; skip those marked "Viewed"; click each unviewed job to load details on the right pane.
   - Extract job metadata: job_id, title, company, location, posted time, URL, seniority, remote flag, viewed flag.
   - Apply company blocklist: drop results whose company name matches blocklist patterns (regex/string match, e.g., Lensa). Log blocklist hit.
   - If `accept_hr_companies` is false, run LLM check to identify if company is a staffing/HR/recruiter firm; if detected, reject, auto-add company to blocklist, log decision.
   - If `requires_sponsorship` is true for this role, run LLM sponsorship filter on the job detail; reject if it says no sponsorship/US citizens only; log decision.
   - If not rejected, run LLM match scoring vs master resume; default accept threshold ≥8/10 (prompt customizable); log score and decision.
7. When a job is accepted:
   - Record in storage (CSV & JSON) with timestamp, score, and source URL.
   - Open a new browser tab; search "role at company_name" on LinkedIn (add random delay 2–5s).
   - Scrape and send connection requests to people matching the role (at least first 3 pages, max 10 requests/page or until page exhausted).
   - Log connection requests sent per page; handle rate limit/failure gracefully; continue to next page.
   - Close the new tab; return to main tab (original search results tab).
   - Send an email alert immediately with key details, score, and link; include connection count in email.
   - Log email sent event.
8. Continue loop; log every step with timestamps and separators; surface retry/backoff events.
9. On graceful shutdown, close Selenium session and persist logs.

## LLM Steps

### Default Prompts (customizable in config or .env)

**1. HR/Staffing Company Detection**
```
Determine if the company "{company_name}" is a staffing, recruitment, HR, or temp agency firm.
Return JSON: {"is_hr_company": true/false, "reason": "brief explanation"}
```

**2. Sponsorship Filter**
```
Review the job description below. Does it state that the company does NOT sponsor visas or does it require US citizenship only?
Job Description:
{job_description}

Return JSON: {"decision": "accept" or "reject", "reason": "brief explanation"}
```

**3. Match Scoring**
```
You are a career advisor. The user's resume and preferences are below.
A job posting follows. On a scale of 0–10, how well does the job match the user's background, goals, and preferences?

User Resume:
{resume_text}

User Preferences (if any):
{preferences_text}

Job Title: {job_title}
Company: {company_name}
Location: {job_location}
Job Description:
{job_description}

Return JSON: {"score": <0-10>, "reasoning": "brief explanation", "verdict": "accept" or "reject"}
```

## Date Posted Custom Range (f_TPR)
- LinkedIn uses `f_TPR=r<seconds>` (e.g., `r86400` for 24h).
- Supported custom range: clamp to 3600–86400 seconds.
- Default for roles: `r3600` (last hour).
- If LinkedIn ignores/clamps values, fall back to standard filters; treat empty results as potential clamp or no roles available.

## Notification Strategy
- Channel: email via Gmail app password (SMTP).
- Content: role, company, location, posted time, match rationale/link.
- Future: rate limiting (max emails/hour) and digest mode.

## Data Storage Format

### matched_jobs.csv
```
job_id, title, company, location, remote, seniority, posted_time, job_url, match_score, matched_at, connections_sent, email_sent
```

### matched_jobs.json (same data, alternative format)
```json
{
  "jobs": [
    {
      "job_id": "unique_id",
      "title": "Software Engineer",
      "company": "Acme Corp",
      "location": "New York, NY",
      "remote": "hybrid",
      "seniority": "Mid-Senior",
      "posted_time": "2025-01-01T10:30:00Z",
      "job_url": "https://linkedin.com/jobs/...",
      "match_score": 8.5,
      "matched_at": "2025-01-01T11:45:00Z",
      "connections_sent": 15,
      "email_sent": true
    }
  ]
}
```

### company_blocklist.json
```json
{
  "companies": [
    "Lensa",
    "Staffing Inc",
    "*.recruiter.com"
  ]
}
```

## Scheduling
- Local: configurable interval, default 30 minutes.
- Cloud: long-running worker with health checks; consider per-role staggering to reduce bursts.

## Logging
- Daily log files named `logs/job_scraper_YYYY-MM-DD.log`; start a new file at 00:00 local time.
- Log every step with timestamps (ISO format); use horizontal separators (e.g., `---`) for readability.
- Examples to log:
  - `[TIMESTAMP] [LOGIN] LinkedIn login attempt...`
  - `[TIMESTAMP] [SCRAPE_ROLE] Searching for role: {role} in {location}`
  - `[TIMESTAMP] [JOB_FOUND] Found job: {title} at {company}`
  - `[TIMESTAMP] [BLOCKLIST_HIT] Rejected due to blocklist: {company}`
  - `[TIMESTAMP] [HR_CHECK] HR/staffing company detected: {company}`
  - `[TIMESTAMP] [SPONSORSHIP] Sponsorship check result: {verdict}`
  - `[TIMESTAMP] [MATCH_SCORE] Job match score: {score}/10, Decision: {verdict}`
  - `[TIMESTAMP] [CONNECTION_REQUEST] Sent {count} connection requests for {role} at {company}`
  - `[TIMESTAMP] [EMAIL_SENT] Alert email sent to {recipient}`
  - `[TIMESTAMP] [ERROR] {error message} [RETRY in {seconds}s]`
  - `===== END OF CYCLE =====` (after each polling cycle)

## Cloud Readiness (Future)
- Containerize scraper + scheduler + notifier.
- Add metrics (scrapes/hour, matches/hour, errors, blocklist hits).
- Add distributed locking if multiple workers run.

## Decisions (locked in); include `accept_hr_companies` boolean (default false).
2) Email transport: Gmail with app password (SMTP).
3) Default polling interval: 30 minutes; default date_posted `r3600`.
4) Custom `r` clamp: 3600–86400 seconds.
5) Storage: keep CSV/JSON for now.
6) No captcha handling planned.
7) No local seen-store; rely on LinkedIn "viewed" markers; company blocklist filtering post-scrape.
8) HR/staffing company detection via LLM; auto-add to blocklist if rejected
7) No local seen-store; rely on LinkedIn "viewed" markers; company blocklist filtering post-scrape.
