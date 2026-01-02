# Implementation Plan (Test-Driven)

## Project Phases

### Phase 0: Foundation (Setup & Config)
**Goal**: Set up project structure, tooling, and configuration files.

**Deliverables**:
- Pixi environment configured (pixi.toml, pyproject.toml)
- Feature-based folder structure created
- `.env` template with required variables
- `data/roles.json` and `data/company_blocklist.json` templates
- Logging utilities (daily rotation, structured format)
- Configuration loader module
- Phase 0 tests (config loading/validation, logging setup/formatting)

**Dependencies**: None.

**Duration**: 1–2 days.

**Test Use Cases** (added):
- Config loads env/JSON, validates required fields/files, thresholds
- Blocklist add/duplicate handled
- Logging creates dirs/files, honors levels, strips emojis, tags categories

---

### Phase 1: LinkedIn Authentication & Session Management
**Goal**: Login to LinkedIn, persist cookies, handle retries gracefully.

**Deliverables**:
- `src/auth/linkedin_auth.py`: login, cookie persistence, retry logic
- `src/auth/session_manager.py`: manage Selenium browser instance
- Retry mechanism with exponential backoff (2s, 4s, 8s, ..., max 30s)
- Cookie file storage/load (`data/.linkedin_cookies.pkl`)
- Error handling for invalid credentials, network timeouts
- Browser: Chrome (headless by default); surface the window if user intervention is needed (e.g., CAPTCHA/2FA)
- Driver: ship `chromedriver` via pixi dependencies; use it when launching the session
- Cookie strategy: try cookies first; on failure fall back to fresh login
- 2FA/CAPTCHA: detect blockages, alert the user to complete manually (handled later; for now we surface the browser and stop)

**Dependencies**: Phase 0.

**Duration**: 2–3 days.

**Test Use Cases** (to be approved):
- Successful login and cookie save
- Retry on network timeout; eventually succeed
- Retry on network timeout; max retries exceeded → graceful failure with log
- Login with invalid credentials → failure handled
- Load existing cookies from file
- Cookie load fails → login again

---

### Phase 2: LinkedIn Job Scraping (List & Details)
**Goal**: Scrape left-pane job list and right-pane job details from LinkedIn search results.

**Deliverables**:
- `src/scraping/search_builder.py`: construct LinkedIn search URLs with filters (date_posted, experience, remote)
- `src/scraping/job_list_scraper.py`: scrape left-pane list, identify unviewed jobs, extract job_id/title/company/location/viewed flag
- `src/scraping/job_detail_scraper.py`: click job, scrape right-pane details (full description, seniority, remote flag, posted time, applicant count, etc.)
- Rate limiting: 2–5s delays between navigations
- Error handling: stale elements, timeout retries, network errors

**Dependencies**: Phase 1.

**Duration**: 3–4 days.

**Test Use Cases** (to be approved):
- Build search URL with various filter combinations (experience, remote, date_posted)
- Build search URL with custom date_posted `r3600`; ensure `f_TPR=r3600` in URL
- Scrape job list from mock/real LinkedIn search; extract unviewed jobs only
- Click job; scrape details from right pane
- Handle stale element exception; retry and scrape again
- Scrape multiple jobs from paginated results

---

### Phase 3: Company Blocklist & HR Company Detection
**Goal**: Filter out blocked companies and detect HR/staffing firms.

**Deliverables**:
- `src/filtering/blocklist.py`: load blocklist, match company names (exact & regex)
- `src/matching/hr_checker.py`: LLM call to detect HR/staffing companies; return JSON decision
- Config flag `REJECT_HR_COMPANIES` (default true). When false, skip HR rejection path.
- Invalid/failed LLM response defaults to **accept** (no rejection, no blocklist add).
- Auto-add rejected HR companies to blocklist file when HR rejection is enabled.
- Logging: every rejection reason, blocklist hits, HR check decisions (cleanly logged). Rejected jobs stop the pipeline and do **not** flow downstream.
- Storage: only persist jobs that are accepted **after scoring** and only after connection requests have been successfully sent (store the job and the successful connection attempts). All rejections are cleanly logged with reason and stop the pipeline.

**Dependencies**: Phase 0 (config/LLM), Phase 2 (job details).

**Duration**: 2 days.

**Test Use Cases** (to be approved):
- Load blocklist; match exact company name
- Match company via regex pattern (e.g., `*recruiter*`)
- LLM HR check: company is HR firm → reject & auto-add (when `REJECT_HR_COMPANIES` true)
- LLM HR check: company is not HR firm → accept
- LLM HR check: `REJECT_HR_COMPANIES` false → skip HR rejection path (accept)
- Invalid JSON from LLM → log error, assume **accept** (no blocklist add)

---

### Phase 4: Sponsorship Filter
**Goal**: If `requires_sponsorship` is true, filter out jobs that don't sponsor visas.

**Deliverables**:
- `src/matching/sponsorship_filter.py`: LLM call to check job description; return JSON decision
- Logging: sponsorship check result (accept/reject)

**Dependencies**: Phase 0 (config/LLM), Phase 2 (job details).

**Duration**: 1 day.

**Test Use Cases** (to be approved):
- LLM sponsorship check: job says "no sponsorship" → reject
- LLM sponsorship check: job says "open to sponsorship" → accept
- LLM sponsorship check: job description is ambiguous → LLM decides
- Sponsorship filter disabled (`requires_sponsorship` false) → skip check

---

### Phase 5: LLM Match Scoring & Job Storage
**Goal**: Score job fit against master resume; accept if score ≥ threshold and immediately persist accepted jobs.

**Deliverables**:
- `src/matching/resume_loader.py`: extract text from `data/resume.docx` via python-docx
- `src/matching/match_scorer.py`: two-pass LLM scoring: first with smaller model (`OPENAI_MODEL`, default `gpt-4o-mini`), and if first-pass score ≥ `JOB_MATCH_RERANK_TRIGGER` (default 8) rerun with larger model (`OPENAI_MODEL_RERANK`, default `gpt-4o`); return JSON score (0–10) and verdict
- Threshold check (default 8); configurable via `.env` or config
- Persist accepted jobs immediately to `data/jobs.xlsx` (append with header if empty; log duplicates)
- Logging: match score, reasoning, verdict, and storage outcome

**Dependencies**: Phase 0 (config/LLM), Phase 2 (job details), Phase 5 (resume loader).

**Duration**: 2–3 days.

**Test Use Cases** (to be approved):
- Load resume PDF; extract text
- LLM match scoring: high-fit job → score 8–10, accept and append to jobs.xlsx
- LLM match scoring: low-fit job → score 0–5, reject (no append)
- LLM match scoring: medium-fit job → score 6–7, reject (below default threshold 8)
- Invalid JSON from LLM → log error, accept job and append

---

### Phase 6: People Search & Networking (New Tab)
**Goal**: After a role is accepted (Phase 5), open a new tab to LinkedIn People search for that role/company, make a list of people to message and send connection requests.

**Deliverables**:
- `src/networking/people_finder.py`: open a new tab, search `"<role-name> at <company-name>"`, click the LinkedIn **People** tab, collect people cards (name, title, profile URL, connection status) from the first 3 pages; derive a `role_match` flag.
- **Match definition (strict)**: `role_match = true` only when the person’s title contains the queried role string (case-insensitive substring of the role phrase). Example: query "data scientist" matches titles containing "data scientist" or "data science"; it does **not** match "ML" or "AI".
- `src/networking/connection_requester.py`: operate in the same people-search tab (do not open individual profiles). For each card:
   - If `role_match` is true: record **Message** availability (do not send), and if **Connect** is present, click **Connect** (no note) and record.
   - If `role_match` is false: if **Connect** is present, click **Connect** (no note) and record.
   - Process up to the first 3 pages (stop earlier if no more pages). Stored actions are only recorded in Phase 6 and will be sent in the Phase 7 email.
- (No messages or notes are sent in Phase 6; only availability and connect clicks are recorded for the Phase 7 email.)
- **Stop conditions**: process up to the first 3 pages; stop early if no further people/pages are available. Close the networking tab (if opened) and return focus to the main tab.
- Rate limiting: 1–2s delay between requests; log attempts, outcomes, counters, and failures per page/person; continue on errors.
- Tab management: **single dedicated networking tab only when explicitly permitted**. Default: reuse current tab (no new tabs auto-open). If user permits, open one networking tab, finish all Phase 6 steps there, then close and return focus.
- Persist outreach records (people cards + actions + role_match) to `data/linkedin_connections.xlsx` for later inclusion in Phase 7 email.

**Dependencies**: Phase 1 (session manager), Phase 2 (job data), Phase 5 (accepted role).

**Duration**: 3–4 days.

**Test Use Cases**:
- Open new tab right after a role is accepted; verify People tab selected for query `"Software Engineer at Acme"`.
- Scrape people cards across first 3 pages; capture name, title, profile URL, connection status, and `role_match` flag.
- Match logic: query "data scientist" matches titles containing "data scientist"/"data science"; does not match "machine learning" or "AI".
- Match handling: when a match has **Message**, log availability only (no send); when **Connect** exists, click connect and record in excel file.
- Non-match handling: when **Connect** exists, click connect and log it; otherwise no action.
- Pagination: process up to 3 pages; if no further pages/people exist, stop.
- Stop logic: stop after first 3 pages or when no more pages exist; tab closes and main tab is active.
- Rate limit respected (1–2s) and attempts logged; failures logged but workflow continues.
- Tab cleanup: close networking tab and return to the main tab.
- People data persisted to `linkedin_connections`.xlsx` with role_match and recorded actions for Phase 7 email.

---

### Phase 7: Email Notifications
**Goal**: Send email alert for accepted jobs via Gmail SMTP.

**Gmail Setup** (prerequisite):
1. Enable 2FA on your Google account: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Create App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Select app: **Mail**, device: **Other (Custom name)** → "Job Scraper"
   - Copy the 16-character password (no spaces)
3. Add to `.env`:
   ```
   EMAIL_SMTP_HOST=smtp.gmail.com
   EMAIL_SMTP_PORT=587
   EMAIL_SENDER=your-email@gmail.com
   EMAIL_PASSWORD=your16charapppassword
   EMAIL_RECIPIENT=your-email@gmail.com
   ```

**Deliverables**:
- `src/notifications/email_notifier.py`: Gmail SMTP connection (TLS), compose email with job details and connection count
- Template: job title, company, location, match score, job URL, connection count, networking summary
- Error handling: SMTP failure, authentication error, retry or log

**Dependencies**: Phase 0 (config/.env), Phases 2 and 5 (job data & storage), Phase 6 (networking summary).

**Duration**: 1–2 days.

**Test Use Cases** (to be approved):
- Send email with valid Gmail SMTP config; verify email received
- SMTP server unreachable → log error, continue
- Invalid app password → authentication error, log and continue
- Invalid email address → SMTP error, log and continue
- Email with all job details, networking counts, and connection count populated

---

### Phase 8: Scheduler & Main Loop
**Goal**: Orchestrate polling loop, manage roles, handle graceful shutdown.

**Deliverables**:
- `src/scheduler/job_scraper_scheduler.py`: main polling loop, cycle through roles, call each phase in order
- `src/cli/main.py`: CLI entry point (e.g., `python -m src.cli.main` or `pixi run scrape`)
- Graceful shutdown: Ctrl+C → close browser, flush logs, exit cleanly
- Default interval: 30 minutes (configurable)
- Log cycle begin/end with separators

**Dependencies**: Phases 1–7.

**Duration**: 2–3 days.

**Test Use Cases** (to be approved):
- Scheduler loads roles and runs 1 full cycle
- Scheduler retries failed role (network error) → resumes next cycle
- Scheduler handles keyboard interrupt; closes browser and logs shutdown
- Scheduler logs cycle start and end with separators
- Poll interval honored (wait 30 minutes before next cycle)

---

### Phase 9: Integration & E2E Testing
**Goal**: Test full workflow end-to-end; validate all components work together.

**Deliverables**:
- Integration tests: mock LinkedIn, LLM, and email to test full flow
- E2E test (manual): run against real LinkedIn with test role; verify job found, matched, networked, alerted, stored
- Verify logging is consistent across all phases

**Dependencies**: All phases 1–8.

**Duration**: 2–3 days.

**Test Use Cases** (to be approved):
- Full workflow: login → scrape list → scrape details → blocklist → HR check → sponsorship → match score & store job → people search & store contacts → email → close tab
- Multiple roles: cycle through 2+ roles in one polling loop
- Handle errors: network timeout during scrape → retry → resume
- Handle errors: LLM call fails → log, continue to next job

---

### Phase 10: Documentation & Deployment Prep
**Goal**: Finalize docs, prepare for cloud deployment.

**Deliverables**:
- User guide: setup, config, run instructions
- Developer guide: module descriptions, testing, extending
- Cloud checklist: containerization, environment variables, logging, health checks
- README updates

**Dependencies**: All phases.

**Duration**: 1–2 days.

---

## Summary Timeline
- **Phases 0–2**: Foundation + Auth + Scraping (6–9 days)
- **Phases 3–5**: Filtering + HR + Matching + Job Storage (5–7 days)
- **Phase 6**: Networking + People Storage (3–4 days)
- **Phase 7**: Email (1–2 days)
- **Phase 8**: Scheduler (2–3 days) — Logging integrated throughout
- **Phase 9**: Integration (2–3 days)
- **Phase 10**: Docs (1–2 days)

**Total**: ~25–35 days (assuming 1 developer, working sequentially).

---

## Logging Strategy (Cross-Cutting Concern)

Logging is **integrated into every phase**, not treated as a separate phase. Each module logs its activities.

### Phase 0: Logger Setup — verify logging in each
- **Integration tests**: component interactions (e.g., scraper → blocker → matcher) — verify log messages are consistent
- **E2E tests**: full workflow (manual initially, automated if feasible) — verify end-to-end logging output
- **Mocking**: LinkedIn, LLM, email, and file I/O will be mocked in unit/integration tests
- **Logging verification**: check log files for correct format, timestamps, separators, and category labels

**Note**: Logging tests are included in each phase's test scenarios (not in a separate phase), as logging is a cross-cutting concern.

### Per-Phase Logging
- **Phase 1 (Auth)**: Log login attempts, cookie load/save, retry events
- **Phase 2 (Scraping)**: Log URL construction, list scrape, detail scrape, pagination, errors
- **Phase 3 (Blocklist & HR)**: Log blocklist hits, HR check decisions, auto-blocklist additions
- **Phase 4 (Sponsorship)**: Log sponsorship check results (accept/reject)
- **Phase 5 (Match Scoring & Job Storage)**: Log match scores, resume load, LLM calls, thresholds, and job appends
- **Phase 6 (Networking & People Storage)**: Log people search, connection requests sent/failed per page, tab management, and contact appends
- **Phase 7 (Email)**: Log email sent events, SMTP errors, retry attempts
- **Phase 8 (Scheduler)**: Log cycle start/end with separators, role processing, errors, retry backoff

### Log Examples
```
[2025-01-01 10:30:45] [INFO] [LOGIN] LinkedIn login attempt for user@example.com
--- Attempt 1 ---
[2025-01-01 10:31:00] [INFO] [SCRAPE_ROLE] Searching for role: Software Engineer in New York, NY
[2025-01-01 10:31:05] [INFO] [JOB_FOUND] Found job: Software Engineer at Acme Corp (ID: 12345)
[2025-01-01 10:31:06] [INFO] [BLOCKLIST_HIT] Rejected: Lensa (company blocklist)
[2025-01-01 10:31:07] [INFO] [HR_CHECK] Company HR Check: Staffing Inc is HR company, rejected & added to blocklist
[2025-01-01 10:31:08] [INFO] [SPONSORSHIP] Sponsorship check: Accepts sponsorship, ACCEPTED
[2025-01-01 10:31:10] [INFO] [MATCH_SCORE] Job match score: 8.5/10, Decision: ACCEPT
[2025-01-01 10:31:11] [INFO] [JOB_STORED] Matched job stored: ID 12345, score 8.5
[2025-01-01 10:31:15] [INFO] [PEOPLE_SEARCH] Searching "Software Engineer at Acme Corp"
[2025-01-01 10:31:30] [INFO] [CONNECTION_REQUEST] Page 1: 8 connection requests sent (2 failed, continued)
[2025-01-01 10:31:45] [INFO] [CONNECTION_REQUEST] Page 2: 7 connection requests sent
[2025-01-01 10:32:00] [INFO] [CONNECTION_REQUEST] Page 3: exhausted, 0 new people
[2025-01-01 10:32:02] [INFO] [CONTACTS_STORED] People outreach stored: 15 records
[2025-01-01 10:32:05] [INFO] [EMAIL_SENT] Alert email sent to user@example.com (connections: 15)
[2025-01-01 10:32:06] [INFO] [CYCLE_END] End of job processing for role 1/2
===== END OF CYCLE =====
```

---

## Testing Approach

Each phase includes specific test use cases (to be approved). Tests will be:
- **Unit tests**: individual components (e.g., search builder, blocklist matcher, LLM calls)
- **Integration tests**: component interactions (e.g., scraper → blocker → matcher)
- **E2E tests**: full workflow (manual initially, automated if feasible)
- **Mocking**: LinkedIn, LLM, email, and file I/O will be mocked in unit/integration tests
