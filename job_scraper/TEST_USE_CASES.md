# Test Use Cases (For Approval)

This document proposes specific test scenarios for each phase. Please review and approve/modify as needed.

---

## Phase 1: LinkedIn Authentication & Session Management

### Unit Tests

1. **test_auth_login_success**
   - Setup: Mock Selenium WebDriver
   - Action: Call `linkedin_auth.login("user@email.com", "password")`
   - Expected: Login succeeds, cookies saved to `data/.linkedin_cookies.pkl`
   - Assert: File exists and contains valid pickle data

2. **test_auth_login_invalid_credentials**
   - Setup: Mock Selenium WebDriver with failed login page
   - Action: Call `linkedin_auth.login("user@email.com", "wrong_password")`
   - Expected: Raise `LinkedInAuthError` with message about invalid credentials
   - Assert: Exception raised and logged

3. **test_auth_retry_on_network_timeout**
   - Setup: Mock Selenium WebDriver to timeout twice, then succeed
   - Action: Call `linkedin_auth.login(...)`
   - Expected: Retry twice with exponential backoff (2s, 4s), then succeed
   - Assert: Success after retries

4. **test_auth_max_retries_exceeded**
   - Setup: Mock Selenium WebDriver to always timeout
   - Action: Call `linkedin_auth.login(...)`
   - Expected: Retry max times (default 5), then raise `LinkedInAuthError`
   - Assert: Exception raised with retry count logged

5. **test_load_cookies_from_file**
   - Setup: Create mock pickle file with valid cookies
   - Action: Call `session_manager.load_cookies()`
   - Expected: Cookies injected into Selenium session
   - Assert: Session manager reports logged-in state

6. **test_load_cookies_file_not_found**
   - Setup: No cookie file exists
   - Action: Call `session_manager.load_cookies()`
   - Expected: Return false, proceed with login
   - Assert: Login method called as fallback

---

## Phase 2: LinkedIn Job Scraping

### Unit Tests

7. **test_search_builder_basic_url**
   - Action: Build URL for "Software Engineer" in "New York, NY"
   - Expected: URL contains role and location parameters
   - Assert: URL structure matches LinkedIn pattern

8. **test_search_builder_with_experience_filter**
   - Action: Build URL with experience levels ["entry", "associate"]
   - Expected: URL includes experience filter parameter
   - Assert: URL contains correct experience codes

9. **test_search_builder_with_custom_date_posted**
   - Action: Build URL with date_posted "r3600"
   - Expected: URL includes `f_TPR=r3600`
   - Assert: Parameter correctly added

10. **test_search_builder_clamp_date_posted**
    - Action: Build URL with date_posted "r2000" (below 3600)
    - Expected: Clamped to "r3600" or error
    - Assert: Validation prevents invalid values

11. **test_job_list_scraper_extracts_jobs**
    - Setup: Mock Selenium WebDriver with sample LinkedIn HTML (left pane)
    - Action: Call `scraper.scrape_list(...)`
    - Expected: Return list of jobs with job_id, title, company, location, viewed flag
    - Assert: Correct number of jobs, fields populated

12. **test_job_list_scraper_filters_viewed_jobs**
    - Setup: Mock HTML with 5 jobs; 2 marked "Viewed"
    - Action: Call `scraper.scrape_list(...)`
    - Expected: Return only 3 unviewed jobs
    - Assert: Viewed jobs filtered out

13. **test_job_list_scraper_handles_stale_element**
    - Setup: Mock Selenium to raise `StaleElementReferenceException` on first attempt
    - Action: Call `scraper.scrape_list(...)`
    - Expected: Retry scraping and succeed
    - Assert: Stale element handled, job extracted

14. **test_job_detail_scraper_extracts_full_details**
    - Setup: Mock Selenium WebDriver with sample right-pane HTML
    - Action: Call `scraper.scrape_detail(..., job_id="123")`
    - Expected: Return job dict with description, seniority, remote flag, posted_time, etc.
    - Assert: All key fields populated correctly

15. **test_job_detail_scraper_handles_timeout**
    - Setup: Mock Selenium to timeout on details page load
    - Action: Call `scraper.scrape_detail(...)`
    - Expected: Retry up to 3 times, then raise error
    - Assert: Timeout handled gracefully

---

## Phase 3: Company Blocklist & HR Company Detection

### Unit Tests

16. **test_blocklist_exact_match**
    - Setup: Load blocklist with "Lensa"
    - Action: Call `blocklist.is_blocked("Lensa")`
    - Expected: Return true
    - Assert: Exact match works

17. **test_blocklist_regex_match**
    - Setup: Load blocklist with "*.recruiter.com"
    - Action: Call `blocklist.is_blocked("acme.recruiter.com")`
    - Expected: Return true
    - Assert: Regex/pattern match works

18. **test_blocklist_add_and_persist**
    - Setup: Empty blocklist
    - Action: Call `blocklist.add("NewCompany")`
    - Expected: Company added and file persisted
    - Assert: Load file again and verify company is there

19. **test_hr_checker_detects_hr_company**
    - Setup: Mock LLM to return `{"is_hr_company": true, "reason": "staffing firm"}`
    - Action: Call `hr_checker.is_hr_company("Staffing Inc")`
    - Expected: Return true
    - Assert: Decision matches LLM response

20. **test_hr_checker_non_hr_company**
    - Setup: Mock LLM to return `{"is_hr_company": false, "reason": "product company"}`
    - Action: Call `hr_checker.is_hr_company("Acme Corp")`
    - Expected: Return false
    - Assert: Decision matches LLM response

21. **test_hr_checker_adds_to_blocklist_on_rejection**
    - Setup: Mock LLM detects HR company; blocklist is empty
    - Action: Call `hr_checker.is_hr_company(...)` and reject
    - Expected: Company auto-added to blocklist
    - Assert: Blocklist file updated

22. **test_hr_checker_invalid_json_from_llm**
    - Setup: Mock LLM to return invalid JSON
    - Action: Call `hr_checker.is_hr_company(...)`
    - Expected: Log error, assume reject (safe default)
    - Assert: Exception caught, rejection logged

---

## Phase 4: Sponsorship Filter

### Unit Tests

23. **test_sponsorship_check_accepts**
    - Setup: Mock LLM to return `{"decision": "accept", "reason": "open to visa sponsorship"}`
    - Action: Call `sponsorship_filter.check(description)`
    - Expected: Return accept
    - Assert: Decision matches LLM

24. **test_sponsorship_check_rejects**
    - Setup: Mock LLM to return `{"decision": "reject", "reason": "US citizens only"}`
    - Action: Call `sponsorship_filter.check(description)`
    - Expected: Return reject
    - Assert: Decision matches LLM

25. **test_sponsorship_filter_disabled**
    - Setup: Config has `requires_sponsorship: false`
    - Action: Call matching pipeline without sponsorship filter
    - Expected: Skip sponsorship check
    - Assert: No sponsorship LLM call made

---

## Phase 5: LLM Match Scoring

### Unit Tests

26. **test_resume_loader_extracts_text**
    - Setup: Create test PDF with sample resume text
    - Action: Call `resume_loader.load("data/test_resume.pdf")`
    - Expected: Return text extracted from PDF
    - Assert: Text matches sample content

27. **test_resume_loader_file_not_found**
    - Setup: No resume file
    - Action: Call `resume_loader.load(...)`
    - Expected: Raise `FileNotFoundError`
    - Assert: Exception caught and logged

28. **test_match_scorer_high_fit_job**
    - Setup: Mock LLM to return `{"score": 8.5, "verdict": "accept"}`
    - Action: Call `match_scorer.score(job_dict, resume_text)`
    - Expected: Accept (score >= 8)
    - Assert: Verdict is accept

29. **test_match_scorer_low_fit_job**
    - Setup: Mock LLM to return `{"score": 4.0, "verdict": "reject"}`
    - Action: Call `match_scorer.score(job_dict, resume_text)`
    - Expected: Reject (score < 8)
    - Assert: Verdict is reject

30. **test_match_scorer_custom_threshold**
    - Setup: Config has `match_score_threshold: 7`
    - Action: Call `match_scorer.score(job_dict, resume_text)` with LLM returning score 7.5
    - Expected: Accept (score >= 7)
    - Assert: Verdict respects custom threshold

31. **test_match_scorer_invalid_json**
    - Setup: Mock LLM to return malformed JSON
    - Action: Call `match_scorer.score(...)`
    - Expected: Log error, assume reject (safe default)
    - Assert: Exception caught, rejection logged

---

## Phase 6: Storage & Persistence

### Unit Tests

32. **test_matched_jobs_store_append**
    - Setup: Empty CSV file
    - Action: Call `store.append(job_dict)` with sample job
    - Expected: Job appended to CSV
    - Assert: File has header + 1 data row

33. **test_matched_jobs_store_append_multiple**
    - Setup: CSV with 1 job
    - Action: Call `store.append(job_dict)` twice more
    - Expected: CSV has header + 3 data rows
    - Assert: All jobs preserved

34. **test_matched_jobs_store_load_all**
    - Setup: CSV with 2 matched jobs
    - Action: Call `store.load_all()`
    - Expected: Return list of 2 job dicts
    - Assert: Data matches CSV content

35. **test_matched_jobs_store_json_format**
    - Setup: Store append to JSON file
    - Action: Load JSON file
    - Expected: Valid JSON with "jobs" array
    - Assert: JSON parseable and matches job data

36. **test_blocklist_store_load**
    - Setup: Blocklist file with 3 companies
    - Action: Call `blocklist_store.load()`
    - Expected: Return list of 3 companies
    - Assert: All companies loaded

37. **test_blocklist_store_add_and_persist**
    - Setup: Blocklist file with 1 company
    - Action: Call `blocklist_store.add("NewCo")`
    - Expected: File updated with 2 companies
    - Assert: Reload and verify both present

---

## Phase 7: Email Notifications

### Unit Tests

38. **test_email_notifier_sends_email**
    - Setup: Mock SMTP server
    - Action: Call `email_notifier.send(job_dict, connections_count=10)`
    - Expected: Email sent with correct subject and body
    - Assert: SMTP send called with correct params

39. **test_email_notifier_smtp_failure**
    - Setup: Mock SMTP to raise connection error
    - Action: Call `email_notifier.send(...)`
    - Expected: Log error, return false
    - Assert: Exception handled gracefully

40. **test_email_notifier_includes_job_details**
    - Setup: Mock SMTP
    - Action: Call `email_notifier.send(job_dict, ...)`
    - Expected: Email body includes job title, company, score, URL
    - Assert: All details in email body

---

## Phase 8: People Search & Networking

### Unit Tests

41. **test_people_finder_opens_new_tab**
    - Setup: Mock Selenium with 2 tabs initially
    - Action: Call `people_finder.search_and_connect(driver, "Engineer", "Acme")`
    - Expected: New tab opened, tab count = 3
    - Assert: Tab count verified

42. **test_people_finder_searches_role_at_company**
    - Setup: Mock Selenium WebDriver
    - Action: Call `people_finder.search_and_connect(...)`
    - Expected: Navigate to search with query "Engineer at Acme"
    - Assert: Correct URL constructed

43. **test_people_finder_scrapes_people_profiles**
    - Setup: Mock HTML with sample people profiles
    - Action: Call scraping logic in people_finder
    - Expected: Extract name, title, URL for each person
    - Assert: Correct data extracted

44. **test_people_finder_sends_connection_requests**
    - Setup: Mock Selenium with 3 people per page, 2 pages
    - Action: Call `people_finder.search_and_connect(...)`
    - Expected: Send max 10 requests per page, up to 3 pages
    - Assert: Connection request count logged

45. **test_people_finder_closes_tab_and_returns**
    - Setup: Main tab + new tab open
    - Action: Call `people_finder.search_and_connect(...)`; after completion
    - Expected: New tab closed, main tab still active
    - Assert: Tab count back to 1

46. **test_people_finder_handles_no_results**
    - Setup: Search returns 0 people
    - Action: Call `people_finder.search_and_connect(...)`
    - Expected: Log "no results", continue (0 connections sent)
    - Assert: Process continues, count = 0

---

## Phase 9: Logging & Observability

### Unit Tests

47. **test_logger_creates_daily_file**
    - Setup: Logger initialized
    - Action: Call `logger.log("INFO", "TEST", "message")`
    - Expected: File created with name `job_scraper_YYYY-MM-DD.log`
    - Assert: File exists in logs directory

48. **test_logger_rotates_at_midnight**
    - Setup: Logger initialized on 2025-01-01
    - Action: Manually set time to 2025-01-02 00:00:01; call `logger.log(...)`
    - Expected: New file created for 2025-01-02
    - Assert: Old file unchanged, new file created

49. **test_logger_format**
    - Setup: Logger initialized
    - Action: Call `logger.log("INFO", "SCRAPE", "found job")`
    - Expected: Log line format is `[YYYY-MM-DD HH:MM:SS] [INFO] [SCRAPE] found job`
    - Assert: Regex matches expected format

50. **test_logger_includes_separators**
    - Setup: Logger initialized
    - Action: Call `logger.log_separator()` (or equivalent)
    - Expected: Write `===== ... =====` to log
    - Assert: Separator appears in log file

---

## Phase 10: Scheduler & Main Loop

### Unit Tests

51. **test_scheduler_loads_config**
    - Setup: .env and roles.json exist with valid data
    - Action: Initialize scheduler
    - Expected: Config loaded without errors
    - Assert: Scheduler has valid config

52. **test_scheduler_single_cycle**
    - Setup: Mock all components (auth, scraper, matcher, notifier)
    - Action: Call `scheduler.run_once()`
    - Expected: Single polling cycle completes
    - Assert: Cycle start/end logged

53. **test_scheduler_multiple_roles**
    - Setup: roles.json has 2 roles
    - Action: Call `scheduler.run_once()`
    - Expected: Both roles processed in single cycle
    - Assert: Each role logged separately

54. **test_scheduler_respects_poll_interval**
    - Setup: Poll interval = 30 minutes
    - Action: Call `scheduler.run()` with mocked time
    - Expected: Wait 30 minutes between cycles
    - Assert: Time.sleep called with 30*60 seconds

55. **test_scheduler_graceful_shutdown**
    - Setup: Scheduler running in background
    - Action: Send SIGINT (Ctrl+C)
    - Expected: Browser closed, logs flushed, process exits
    - Assert: No hanging processes

---

## Integration Tests (Phase 11)

### Integration Tests

56. **test_full_workflow_one_job**
    - Setup: Mock LinkedIn with 1 job; mock LLM with accept; mock SMTP
    - Action: Run `scheduler.run_once()`
    - Expected: Job scraped → stored → email sent
    - Assert: Matched jobs file has 1 entry, email logged

57. **test_full_workflow_multiple_jobs_with_filters**
    - Setup: Mock LinkedIn with 5 jobs; blocklist has 1; LLM rejects 1; accepts 3
    - Action: Run `scheduler.run_once()`
    - Expected: 3 jobs accepted, emails sent
    - Assert: Matched jobs file has 3 entries

58. **test_full_workflow_with_hr_rejection**
    - Setup: Mock LLM to detect HR company
    - Action: Run `scheduler.run_once()`
    - Expected: Job rejected, company auto-added to blocklist
    - Assert: Blocklist file updated

59. **test_full_workflow_people_search**
    - Setup: Mock LinkedIn, LLM, people search
    - Action: Run `scheduler.run_once()` with accepted job
    - Expected: New tab opened, people searched, connections sent, tab closed
    - Assert: Connection count in matched jobs file

60. **test_error_recovery_during_scrape**
    - Setup: First job scrape fails with timeout; second job succeeds
    - Action: Run `scheduler.run_once()`
    - Expected: First job skipped with log; second job processed
    - Assert: Scheduler continues despite error

---

## Summary

Total: **60 test scenarios**
- Unit tests: 50
- Integration tests: 10

Please review and provide feedback on:
1. Are these test scenarios comprehensive?
2. Any gaps or redundancies?
3. Any scenarios you'd like added or removed?
4. Mocking strategy: acceptable to mock all external dependencies?
5. Should we have E2E tests against real LinkedIn (separate, manual testing)?

Once approved, we'll use these as the test roadmap during implementation.
