"""
LinkedIn job scraper with proper UI handling and 'Viewed' status detection
"""

import math
import os
import re
import time
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions

from .base_scraper import BaseScraper


class LinkedInScraper(BaseScraper):
    """
    Scraper for LinkedIn job listings with UI handling and 'Viewed' status detection.

    Attributes:
        base_url (str): LinkedIn base URL.
        user_email (str): User email for LinkedIn login.
        user_password (str): User password for LinkedIn login.
        driver (webdriver.Chrome): Selenium WebDriver instance.
        authenticated (bool): Login status flag.
        wait (WebDriverWait): Selenium wait object for element loading.
        config: Configuration object loaded from config/config.py.
        blocklist: Blocklist instance for filtering companies.
        hr_checker: HRChecker instance for HR/staffing company detection.
        sponsorship_filter: SponsorshipFilter instance for visa eligibility.
    """

    def __init__(self):
        """
        Initialize LinkedInScraper with config, blocklist, HR checker, and sponsorship filter.
        Loads credentials from environment variables.
        """
        super().__init__("linkedin")
        self.base_url = "https://www.linkedin.com"
        self.user_email = os.getenv("LINKEDIN_EMAIL", "")
        self.user_password = os.getenv("LINKEDIN_PASSWORD", "")
        from typing import cast

        from selenium.webdriver.support.ui import WebDriverWait

        self.driver = cast(webdriver.Chrome, None)
        self.authenticated = False
        self.wait = cast(WebDriverWait, None)
        from config.config import get_config
        from filtering.blocklist import Blocklist
        from matching.hr_checker import HRChecker
        from matching.sponsorship_filter import SponsorshipFilter

        self.config = get_config()
        self.blocklist = Blocklist(config=self.config, logger=self.logger)
        self.hr_checker = HRChecker(
            config=self.config, blocklist=self.blocklist, logger=self.logger
        )
        self.sponsorship_filter = SponsorshipFilter(
            config=self.config, logger=self.logger
        )

        if self.user_email and self.user_password:
            self.logger.info(f"🔐 LinkedIn credentials found: {self.user_email}")
        else:
            self.logger.warning("⚠️  No LinkedIn credentials in .env")

    def _setup_driver(self):
        """Initialize Selenium WebDriver with proper options"""
        if self.driver:
            return

        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            # Always run headless unless config.headless is explicitly False
            if getattr(self.config, "headless", True):
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")

            self.driver = webdriver.Chrome(options=options)
            from selenium.webdriver.support.ui import WebDriverWait

            self.wait = WebDriverWait(self.driver, 15)
            self.logger.debug("Chrome WebDriver initialized (fresh profile)")
        except Exception as exc:
            self.logger.error(f"Failed to initialize WebDriver: {exc}")
            raise

    def _login(self) -> bool:
        """Login to LinkedIn"""
        from selenium.common.exceptions import TimeoutException

        if not self.user_email or not self.user_password:
            return False

        if self.authenticated:
            return True

        try:
            self._setup_driver()
            self.logger.info(f"🔑 Attempting login to LinkedIn as {self.user_email}...")

            self.driver.get(f"{self.base_url}/login")
            time.sleep(2)

            email_field = self.wait.until(
                expected_conditions.presence_of_element_located((By.ID, "username"))
            )
            email_field.send_keys(self.user_email)

            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(self.user_password)

            login_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            login_button.click()
            time.sleep(4)

            try:
                self.wait.until(
                    expected_conditions.presence_of_element_located(
                        (By.CLASS_NAME, "global-nav")
                    )
                )
                self.authenticated = True
                self.logger.info(
                    f"✅ Successfully logged in to LinkedIn as {self.user_email}"
                )
                return True
            except TimeoutException:
                self.logger.error("❌ Login failed")
                return False
        except Exception as exc:
            self.logger.error(f"❌ Login error: {exc}")
            return False

    def scrape(
        self,
        max_applicants: int = 100,
        scorer=None,
        match_threshold: float = 0.0,
        storage=None,
        connect_pages: int | None = None,
        connect_delay_range: tuple[float, float] = (1.0, 2.0),
        resume_text: str = "",
    ) -> list[dict[str, Any]]:
        """Main scraping method with inline scoring/export/connect."""
        self.logger.info("=" * 60)
        self.logger.info("🚀 Starting LinkedIn scraper")
        self.logger.info("=" * 60)

        jobs: list[dict[str, Any]] = []
        configured_roles = []
        try:
            configured_roles = self.config.get_enabled_roles()
        except Exception:
            configured_roles = []

        if not configured_roles:
            self.logger.warning(
                "No enabled roles found in roles.json; skipping LinkedIn scrape."
            )
            return jobs

        try:
            if not self._login():
                self.logger.warning("Cannot proceed without login")
                return jobs

            self.logger.info(f"📋 Scraping {len(configured_roles)} job queries...")

            seen_titles = set()
            for role in configured_roles:
                title = role.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                # Query-related fields from roles.json, with defaults
                location = role.get("location") or os.getenv(
                    "DEFAULT_LOCATION", "United States"
                )
                experience_levels = role.get("experience_levels") or [
                    "Entry level",
                    "Associate",
                ]
                date_posted = role.get("date_posted") or os.getenv(
                    "DEFAULT_DATE_POSTED",
                    self.config.search_settings.get("date_posted", "r86400"),
                )
                # Threshold/limit fields from .env/config, with defaults
                try:
                    max_applicants_val = int(
                        os.getenv("MAX_APPLICANTS", str(max_applicants))
                    )
                except Exception:
                    max_applicants_val = 100
                try:
                    match_threshold_val = float(
                        os.getenv("JOB_MATCH_THRESHOLD", str(match_threshold))
                    )
                except Exception:
                    match_threshold_val = 0.0
                try:
                    no_match_pages_threshold_val = int(
                        os.getenv("NO_MATCH_PAGES_THRESHOLD", "8")
                    )
                except Exception:
                    no_match_pages_threshold_val = 8
                try:
                    connect_pages_val = int(
                        os.getenv(
                            "CONNECT_PAGES_THRESHOLD",
                            str(connect_pages if connect_pages is not None else 3),
                        )
                    )
                except Exception:
                    connect_pages_val = 3

                self.logger.info(
                    f"🔎 Searching for: '{title}' | Location: '{location}' | Experience: {experience_levels} | Date Posted: {date_posted} | Max Applicants: {max_applicants_val} | Match Threshold: {match_threshold_val} | No Match Pages: {no_match_pages_threshold_val} | Connect Pages: {connect_pages_val}"
                )
                page_jobs, matched = self._scrape_query(
                    title,
                    max_applicants_val,
                    scorer=scorer,
                    match_threshold=match_threshold_val,
                    storage=storage,
                    connect_pages=connect_pages_val,
                    connect_delay_range=connect_delay_range,
                    no_match_pages_threshold=no_match_pages_threshold_val,
                    location=location,
                    experience_levels=experience_levels,
                    date_posted=date_posted,
                    resume_text=resume_text,
                )
                self.logger.info(f"✅ Processed {len(page_jobs)} jobs for '{title}'")
                jobs.extend(page_jobs)

            self.logger.info("=" * 60)
            self.logger.info(f"✨ LinkedIn scrape complete: {len(jobs)} jobs total")
            self.logger.info("=" * 60)
            self._log_scrape_result(len(jobs))

        except Exception as exc:
            self.logger.error(f"Critical error in scrape: {exc}")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    self.logger.debug("WebDriver closed")
                except Exception:
                    pass

        return jobs

    def setup_driver(self, driver: webdriver.Chrome, wait_time: float = 10.0):
        """Set up the Selenium driver and WebDriverWait."""
        from selenium.webdriver.support.ui import WebDriverWait

        self.driver = driver
        self.wait = WebDriverWait(self.driver, wait_time)

    def _scrape_query(
        self,
        query: str,
        max_applicants: int,
        scorer=None,
        match_threshold: float = 0.0,
        storage=None,
        connect_pages: int | None = 3,
        connect_delay_range: tuple[float, float] = (1.0, 2.0),
        no_match_pages_threshold: int | None = None,
        location: str = "United States",
        experience_levels: list[str] | None = None,
        date_posted: str | None = None,
        resume_text: str = "",
    ) -> tuple[list[dict[str, Any]], bool]:
        """Scrape jobs for a single query; return (jobs, matched_flag)."""
        jobs: list[dict[str, Any]] = []
        matched = False
        traversed_jobs = 0
        current_page = 1
        if not date_posted:
            date_posted = self.config.search_settings.get("date_posted", "r86400")
        search_url = self._build_search_url(
            keywords=query,
            location=location,
            date_posted=date_posted,
            experience_levels=experience_levels,
            start=0,
        )
        self.logger.info("=" * 60)
        self.logger.info(f"  📄 Page 1 for '{query}' (start=0)")
        self.logger.debug(f"  Navigating to: {search_url}")
        if not self._safe_get(search_url):
            self.logger.error("  Could not navigate to search URL; aborting query")
            return jobs, matched
        # Extract total jobs for query
        total_jobs_for_query = self._get_total_results()
        self.logger.info(
            f"Total jobs available for query '{query}': {total_jobs_for_query}"
        )

        # Get threshold from env if not provided
        if no_match_pages_threshold is None:
            try:
                no_match_pages_threshold = int(os.getenv("NO_MATCH_PAGES_THRESHOLD", 8))
            except Exception:
                no_match_pages_threshold = 8

        # Track number of jobs rejected due to blocklist or HR company per page
        rejected_blocklist_hr_count = 0
        while True:
            page_state = self._get_page_state()
            self.logger.debug(f"[PAGINATION] get_page_state() returned: {page_state}")
            if page_state and page_state[0]:
                current_page = page_state[0]
                self.logger.debug(
                    f"[PAGINATION] Updated current_page to: {current_page}"
                )

            search_url = self.driver.current_url
            start = (current_page - 1) * 25
            self.logger.info("=" * 60)
            self.logger.info(f"  📄 Page {current_page} for '{query}' (start={start})")
            self.logger.debug(
                f"[PAGINATION] Starting scrape for page {current_page}, query: '{query}', start: {start}"
            )

            try:
                self.wait.until(
                    expected_conditions.presence_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            "ul.scaffold-layout__list, div.jobs-search-results-list",
                        )
                    )
                )
            except Exception:
                self.logger.debug("  Job list did not become visible in time")

            self._wait_for_results_loader()
            import time

            time.sleep(3)
            self._scroll_job_list(target_count=25)
            job_cards = self._get_job_cards(target_count=25)

            # Only force scroll if we haven't traversed all jobs for the query
            # If total_jobs_for_query is known and traversed_jobs + len(job_cards) >= total_jobs_for_query, do not force scroll
            if len(job_cards) < 25:
                if (
                    total_jobs_for_query is not None
                    and (traversed_jobs + len(job_cards)) >= total_jobs_for_query
                ):
                    self.logger.info(
                        f"  All {total_jobs_for_query} jobs traversed for query '{query}'. No need to force scroll."
                    )
                else:
                    self.logger.info(
                        f"  ⚠️ Only {len(job_cards)} job cards loaded; forcing more scrolls"
                    )
                    for _ in range(3):
                        self._scroll_job_list(target_count=25)
                        time.sleep(1)
                        job_cards = self._get_job_cards(target_count=25)
                        if len(job_cards) >= 25:
                            break

            if not job_cards:
                self.logger.info("  No job cards found on this page; ending scrape.")
                break

            for idx in range(len(job_cards)):
                company_name = None
                try:
                    self.logger.info("=" * 60)
                    job_cards = self._get_job_cards()
                    if idx >= len(job_cards):
                        break
                    job_card = job_cards[idx]
                    traversed_jobs += 1
                    self.logger.info(
                        f"  ▶️ Job card {idx + 1}/{len(job_cards)} on page {current_page}"
                    )
                    self.logger.debug(
                        f"  Processing job {idx + 1}/{len(job_cards)} on page {current_page}"
                    )
                    if self._is_viewed(job_card):
                        self.logger.info("    ⏭️  Skipped: Already viewed job card")
                        continue
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView(true);", job_card
                        )
                        self.logger.info("=" * 60)
                        job_cards = self._get_job_cards()
                        if idx >= len(job_cards):
                            break
                        job_card = job_cards[idx]
                        traversed_jobs += 1
                        self.logger.info(
                            f"  ▶️ Job card {idx + 1}/{len(job_cards)} on page {current_page}"
                        )
                        self.logger.debug(
                            f"  Processing job {idx + 1}/{len(job_cards)} on page {current_page}"
                        )
                        if self._is_viewed(job_card):
                            self.logger.info("    ⏭️  Skipped: Already viewed job card")
                            continue
                        try:
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView(true);", job_card
                            )
                            time.sleep(0.5)
                            try:
                                link = job_card.find_element(
                                    By.CSS_SELECTOR,
                                    "a.job-card-list__title, a.app-aware-link",
                                )
                                link.click()
                            except Exception:
                                job_card.click()
                            self._wait_for_results_loader()
                            time.sleep(1.2)
                            self._scroll_right_panel()
                            time.sleep(1)
                            time.sleep(2)
                            # Wait for right-pane container and a title element (anchor or h1)
                            details_ready = False
                            for _ in range(6):
                                try:
                                    # Try both anchor and non-anchor selectors
                                    title_elem = None
                                    try:
                                        title_elem = self.driver.find_element(
                                            By.CSS_SELECTOR,
                                            "h1 a, h1, div.job-details-jobs-unified-top-card__job-title a, div.job-details-jobs-unified-top-card__job-title",
                                        )
                                    except Exception:
                                        pass
                                    if title_elem and title_elem.text.strip():
                                        details_ready = True
                                        break
                                except Exception:
                                    pass
                                time.sleep(0.5)
                            if not details_ready:
                                self.logger.warning(
                                    "    ⚠️ Job details pane not ready after click; skipping this card."
                                )
                                self._close_extra_tabs()
                                self._safe_back_to_results(search_url)
                                continue
                            # Extract job details after confirming details_ready
                            job = self._extract_job_details()
                            if not job:
                                self.logger.info(
                                    "    ❌ Skipped: Could not extract job details from card"
                                )
                                self._close_extra_tabs()
                                self._safe_back_to_results(search_url)
                                continue
                            description = job.get("description", "")
                        except Exception as job_exc:
                            self.logger.warning(
                                f"Failed to process job card {idx + 1}: {job_exc}"
                            )
                            self._close_extra_tabs()
                            self._safe_back_to_results(search_url)
                            continue
                    except StaleElementReferenceException:
                        self.logger.debug("    Stale element, continuing...")
                        self._close_extra_tabs()
                        self._safe_back_to_results(search_url)
                        continue
                    # Only one except block for Exception is needed
                    normalized_company = (
                        company_name.strip().lower() if company_name else ""
                    )
                    # Check blocklist with normalized name and original name
                    if company_name and (
                        self.blocklist.is_blocked(company_name)
                        or self.blocklist.is_blocked(normalized_company)
                    ):
                        self.logger.info(
                            f"    ❌ Rejected: {company_name} blocked (no downstream processing)"
                        )
                        rejected_blocklist_hr_count += 1
                        self._close_extra_tabs()
                        self._safe_back_to_results(search_url)
                        continue

                    hr_result = self.hr_checker.check(
                        company_name or "", description=description
                    )
                    if hr_result.get("is_hr_company"):
                        self.logger.info(
                            f"    ❌ Rejected: {company_name} flagged as HR/staffing. Reason: {hr_result.get('reason', '')}"
                        )
                        rejected_blocklist_hr_count += 1
                        self._close_extra_tabs()
                        self._safe_back_to_results(search_url)
                        continue

                    sponsor = self.sponsorship_filter.check(description)
                    if not sponsor.get("accepts_sponsorship", True):
                        self.logger.info(
                            f"    ❌ Rejected: Sponsorship/eligibility: {self._short_reason(sponsor.get('reason', ''))}"
                        )
                        self._close_extra_tabs()
                        self._safe_back_to_results(search_url)
                        continue

                    score = None
                    if scorer:
                        try:
                            with open(
                                os.path.join(
                                    os.path.dirname(__file__),
                                    "../data/LLM_base_score.txt",
                                ),
                                "r",
                                encoding="utf-8",
                            ) as f:
                                llm_prompt = f.read().strip()
                        except Exception as exc:
                            self.logger.error(
                                f"    Could not read LLM prompt template: {exc}"
                            )
                            llm_prompt = ""
                        try:
                            score = float(scorer(job, prompt=llm_prompt))
                        except Exception as exc:
                            self.logger.error(f"    LLM scoring failed: {exc}")
                            score = 0.0
                        job["match_score"] = score
                        reason = self._short_reason(job.get("match_reason", ""))
                        # If LLM says to add to blocklist, add company
                        if reason == "Add to blocklist":
                            self.blocklist.add(company_name or "")
                            self.logger.info(
                                f"    🚫 Added {company_name} to blocklist via LLM match_reason."
                            )
                            rejected_blocklist_hr_count += 1
                        if job.get("reranked"):
                            rerank_reason = self._short_reason(
                                job.get("match_reason_rerank", "")
                            )
                            self.logger.info(
                                f"    LLM base score {job.get('first_score', score):.1f} -> rerank {score:.1f} (threshold {match_threshold}): {rerank_reason or reason}"
                            )
                        else:
                            self.logger.info(
                                f"    LLM score {score:.1f} (threshold {match_threshold}): {reason}"
                            )
                        if score < match_threshold:
                            self.logger.info(
                                f"    ❌ Skipped: LLM score {score:.1f} < {match_threshold}"
                            )
                            self._close_extra_tabs()
                            self._safe_back_to_results(search_url)
                            continue
                    if storage:
                        storage.add_job(job)
                    jobs.append(job)
                    self._close_extra_tabs()
                    self._safe_back_to_results(search_url)
                    matched = True
                    continue
                except StaleElementReferenceException:
                    self.logger.debug("    Stale element, continuing...")
                    self._close_extra_tabs()
                    self._safe_back_to_results(search_url)
                    continue
                except Exception as exc:
                    self.logger.debug(f"    Error processing job: {exc}")
                    self._close_extra_tabs()
                    self._safe_back_to_results(search_url)
                    continue

            # Try to go to next page; if not possible, break
            if not self._go_to_next_page(current_page=current_page):
                self.logger.info(
                    f"  No more pages after page {current_page} for '{query}'"
                )
                break

            current_page += 1

            # Early exit: if all 25 jobs on page are rejected due to blocklist or HR company, skip to next role
            if rejected_blocklist_hr_count >= 25:
                self.logger.info(
                    f"  ⏹️ All 25 jobs on page rejected due to blocklist/HR company for '{query}'; skipping to next role."
                )
                break

        if not matched:
            self.logger.info(
                f"  No matches yet after page {current_page} for '{query}'"
            )

        return jobs, matched

    @staticmethod
    def _short_reason(reason: str) -> str:
        """Return up to two sentences for concise logging."""

        if not reason:
            return "No reason provided"

        import re

        sentences = re.split(r"(?<=[.!?])\s+", reason.strip())
        joined = " ".join(sentences[:2]).strip()
        return joined or reason.strip()[:240]

    def _scroll_right_panel(self):
        """Scroll the right job details panel to the bottom to load all content, ensuring visibility first."""
        try:
            if self.driver is None:
                self.logger.debug("Driver not set; cannot scroll right panel.")
                return
            panel_selectors = [
                "div.jobs-search__job-details--container",
                "div.jobs-details__main-content",
                "div.jobs-search__right-rail",
            ]
            for selector in panel_selectors:
                try:
                    panel = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.driver.execute_script(
                        "arguments[0].scrollTop = arguments[0].scrollHeight", panel
                    )
                    time.sleep(0.5)
                    return
                except Exception:
                    continue
        except Exception as exc:
            self.logger.debug(f"Could not scroll right panel: {exc}")

    def _safe_back_to_results(self, search_url: str):
        """Return to results page after viewing a job."""
        try:
            if self.driver is not None:
                self.driver.back()
                time.sleep(2)
            else:
                raise Exception("Driver is None")
        except Exception:
            try:
                self._safe_get(search_url)
            except Exception:
                self.logger.debug("Could not navigate back to results")

    def _close_extra_tabs(self):
        """Close all tabs except the first/main one."""
        try:
            if self.driver is None:
                self.logger.debug("Driver not set; cannot close extra tabs.")
                return
            handles = self.driver.window_handles
            if len(handles) <= 1:
                return
            main = handles[0]
            for handle in handles[1:]:
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                except Exception:
                    continue
            self.driver.switch_to.window(main)
        except Exception as exc:
            self.logger.debug(f"    Could not close extra tabs: {exc}")

    def _build_search_url(
        self,
        keywords: str = "",
        location: str = "United States",
        date_posted: str | None = "r86400",
        experience_levels: list[str] | None = None,
        start: int = 0,
    ) -> str:
        """Build LinkedIn job search URL with explicit filters for keywords, location, date_posted (f_TPR), and experience_levels (f_E)."""
        from urllib.parse import quote

        base = f"{self.base_url}/jobs/search/?"
        params = []
        if keywords:
            params.append(f"keywords={quote(keywords)}")
        if location:
            params.append(f"location={quote(location)}")
        if date_posted:
            params.append(f"f_TPR={date_posted}")
        if experience_levels:
            exp_map = {
                "Internship": "1",
                "Entry level": "2",
                "Associate": "3",
                "Mid-Senior level": "4",
                "Director": "5",
                "Executive": "6",
            }
            codes = [exp_map.get(level) for level in experience_levels]
            codes = [code for code in codes if code is not None]
            if codes:
                params.append(f"f_E={','.join(codes)}")
        params.append("sortBy=DD")
        if start:
            params.append(f"start={start}")
        return base + "&".join(params)

    def _scroll_job_list(self, target_count: int = 25):
        """Scroll the job list to load up to target_count cards with extra retries."""

        try:
            if self.driver is None:
                self.logger.debug("Driver not set; cannot scroll job list.")
                return
            selectors = [
                "div.jobs-search-results-list",
                "ul.scaffold-layout__list",
                "[data-search-results-container]",
                "section[data-view-id='job-search-results']",
            ]

            container = None
            for selector in selectors:
                try:
                    container = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except Exception:
                    continue

            last_count = len(self._get_job_cards(target_count=target_count))
            stagnant_rounds = 0

            for _ in range(24):
                if target_count and last_count >= target_count:
                    break

                if container:
                    self.driver.execute_script(
                        "arguments[0].scrollTop = arguments[0].scrollHeight",
                        container,
                    )
                else:
                    # Fallback to window scroll if container not found
                    self.driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);"
                    )

                time.sleep(0.6)
                self._wait_for_results_loader()
                new_count = len(self._get_job_cards(target_count=target_count))

                if new_count <= last_count:
                    stagnant_rounds += 1
                    try:
                        self.driver.execute_script("window.scrollBy(0, 600);")
                    except Exception:
                        pass
                    time.sleep(0.3)
                    new_count = len(self._get_job_cards(target_count=target_count))
                else:
                    stagnant_rounds = 0

                if new_count == last_count and stagnant_rounds >= 4:
                    # Likely no more items to load
                    break

                last_count = new_count
        except Exception as exc:
            self.logger.debug(f"Could not scroll job list: {exc}")

    def _wait_for_results_loader(self):
        """Best-effort wait for the results loader to clear after scrolling."""
        try:
            if self.driver is None:
                return
            loader_selectors = [
                "div.jobs-search-results-list__loader",
                "div.artdeco-loader",
                "div.scaffold-layout__list-spinner",
                "div[data-test-results-loader]",
            ]

            for _ in range(6):
                active = False
                for selector in loader_selectors:
                    try:
                        loaders = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if any(loader.is_displayed() for loader in loaders):
                            active = True
                            break
                    except Exception:
                        continue

                if not active:
                    break

                time.sleep(0.25)
        except Exception:
            # Non-fatal; continue without blocking
            pass

    def _get_page_state(self) -> tuple[int | None, int | None]:
        """Return (current_page, total_pages) from the pagination state element."""

        if self.driver is None:
            return None, None
        selectors = [
            "p.jobs-search-pagination__page-state",
            "div.jobs-search-pagination__page-state",
            "div[data-test-pagination-page-state]",
            "li.artdeco-pagination__indicator--number",
        ]
        try:
            for selector in selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                except Exception:
                    continue

                text = (elem.text or "").strip().lower()
                if not text:
                    continue

                patterns = [
                    r"page\s+(\d+)\s+of\s+(\d+)",
                    r"(\d+)\s*/\s*(\d+)",
                ]

                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        current = int(match.group(1))
                        total = int(match.group(2))
                        return current, total

            # Fallback: infer from numbered pagination indicators
            try:
                indicators = self.driver.find_elements(
                    By.CSS_SELECTOR, "li.artdeco-pagination__indicator--number"
                )
                active = [
                    el
                    for el in indicators
                    if (el.get_attribute("aria-current") or "").lower() == "true"
                    or "active" in (el.get_attribute("class") or "")
                ]
                if indicators and active:
                    current_num = int((active[0].text or "0").strip() or 0)
                    totals = [
                        int((el.text or "0").strip())
                        for el in indicators
                        if (el.text or "").strip().isdigit()
                    ]
                    if totals:
                        return current_num or None, max(totals)
            except Exception:
                pass
        except Exception as exc:
            self.logger.debug(f"Could not parse page state: {exc}")

        return None, None

    def _get_total_results(self) -> int:
        """Parse the total results count from the subtitle element."""

        if self.driver is None:
            return 0
        selectors = [
            "div.jobs-search-results-list__subtitle span",
            "div.jobs-search-results-list__subtitle",
            "span.results-context-header__job-count",
            "h1>span[data-test-search-result]",
            "h1>span",
        ]

        try:
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                except Exception:
                    continue

                for elem in elements:
                    text = (elem.text or "").strip() or (
                        elem.get_attribute("innerText") or ""
                    ).strip()
                    if not text:
                        continue

                    match = re.search(r"([0-9,]+)\s+result", text.lower())
                    if match:
                        return int(match.group(1).replace(",", ""))

                    match = re.search(r"([0-9,]+)\s+job", text.lower())
                    if match:
                        return int(match.group(1).replace(",", ""))
        except Exception as exc:
            self.logger.debug(f"Could not parse total results: {exc}")

        return 0

    @staticmethod
    def _compute_total_pages(
        total_results: int, page_size: int = 25, cap: int | None = None
    ) -> int:
        """Compute page count with optional cap for predictable pagination math."""

        if total_results <= 0 or page_size <= 0:
            return 0

        pages = math.ceil(total_results / page_size)
        if cap is not None:
            pages = min(pages, cap)

        return pages

    def _go_to_next_page(self, current_page: int | None = None) -> bool:
        """Click the next-page button with retries and wait for the page to advance."""

        selectors = [
            "button.jobs-search-pagination__button--next",
            "button[aria-label='View next page']",
            "button[aria-label='Next']",
            "li.artdeco-pagination__indicator--number+li button",
        ]

        if self.driver is None or self.wait is None:
            self.logger.debug("Driver or wait not set; cannot go to next page.")
            return False
        before_url = self.driver.current_url
        self.logger.debug(
            f"[PAGINATION] Attempting to go to next page from URL: {before_url}, current_page: {current_page}"
        )

        for attempt in range(3):
            self.logger.debug(
                f"[PAGINATION] Next-page navigation attempt {attempt + 1} (current_page: {current_page})"
            )
            for selector in selectors:
                try:
                    self.logger.debug(f"[PAGINATION] Trying selector: {selector}")
                    button = self.wait.until(
                        expected_conditions.element_to_be_clickable(
                            (By.CSS_SELECTOR, selector)
                        )
                    )
                    button.click()
                    self.logger.debug(
                        f"[PAGINATION] Clicked next-page button with selector: {selector}"
                    )
                    time.sleep(0.5)
                    break
                except Exception as e:
                    self.logger.debug(
                        f"[PAGINATION] Selector failed: {selector}, error: {e}"
                    )
                    continue
            else:
                continue

            try:
                self._wait_for_results_loader()
                self.logger.debug("[PAGINATION] Waiting for page to advance...")
                self.wait.until(
                    lambda d: (
                        (current_page is None)
                        or (self._get_page_state()[0] not in [None, current_page])
                        or d.current_url != before_url
                    )
                )
                after_url = self.driver.current_url
                self.logger.debug(
                    f"[PAGINATION] Page advanced to URL: {after_url}, previous: {before_url}"
                )
                time.sleep(1.2)
                return True
            except Exception as exc:
                self.logger.debug(
                    f"[PAGINATION] Next-page navigation attempt {attempt + 1} failed to advance: {exc} (current_page: {current_page}, URL: {self.driver.current_url})"
                )
                time.sleep(1.0)

        self.logger.warning(
            f"[PAGINATION] Could not click or advance to next page (current_page: {current_page}, URL: {self.driver.current_url})"
        )
        return False

    def _get_job_cards(self, target_count: int = 25) -> list:
        """Collect up to target_count unique, visible job card elements."""

        if self.driver is None:
            return []
        selectors = [
            "[data-job-id]",
            "article[data-job-id]",
            "div[data-view-id='job-card']",
            "div.job-card-container",
            "div.job-card-container--clickable",
            "div.base-card",
            "li.jobs-search-results__list-item",
            "li.jobs-search-results__list-item.occludable-update",
            "li.scaffold-layout__list-item",
            "li.artdeco-list__item",
        ]

        cards: list = []
        seen: set[str] = set()

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if not elem.is_displayed():
                        continue

                    key = (
                        elem.get_attribute("data-job-id")
                        or elem.get_attribute("data-occludable-job-id")
                        or elem.get_attribute("data-entity-urn")
                        or elem.get_attribute("id")
                        or getattr(elem, "id", None)
                    )

                    if not key:
                        key = str(hash(elem))

                    if key in seen:
                        continue

                    seen.add(key)
                    cards.append(elem)

                    if target_count and len(cards) >= target_count:
                        return cards
            except Exception:
                continue

        return cards

    def _is_viewed(self, job_card) -> bool:
        """Check if job card has 'Viewed' indicator"""
        try:
            card_text = job_card.text.lower()
            if "viewed" in card_text:
                return True
            viewed_selectors = [
                "span.job-card-container__footer-job-state",
                "span.job-card-list__footer-wrapper",
                "li.job-card-container__footer-item",
            ]
            for selector in viewed_selectors:
                try:
                    elements = job_card.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if "viewed" in elem.text.lower():
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def _extract_job_details(self) -> dict[str, Any] | None:
        """Extract job details from the job details panel, using broader selectors and logging when pane is empty."""
        try:
            if self.driver is None:
                self.logger.debug("Driver not set; cannot extract job details.")
                return None
            details: dict[str, Any] = {}
            # Broaden selectors: include non-anchor h1/h2 for title, span/div for company
            title_selectors = [
                "div.job-details-jobs-unified-top-card__job-title h1 a",
                "h1.job-details-jobs-unified-top-card__job-title a",
                "h1.jobs-unified-top-card__job-title a",
                "h1.t-24.t-bold.inline a",
                "h2.t-24",
                "h1.job-details-jobs-unified-top-card__job-title",
                "h1.jobs-unified-top-card__job-title",
                "h1.t-24.t-bold.inline",
                "h1",
            ]
            details["title"] = self._safe_find_text_multi(title_selectors)
            company_selectors = [
                "div.job-details-jobs-unified-top-card__company-name a",
                "a.job-details-jobs-unified-top-card__company-name",
                "a.jobs-unified-top-card__company-name",
                "span.jobs-unified-top-card__company-name",
                "div.job-details-jobs-unified-top-card__company-name",
                "span.jobs-unified-top-card__company-name",
                "div.jobs-unified-top-card__company-name",
                "span.t-16.t-black.t-bold",
            ]
            details["company"] = self._safe_find_text_multi(company_selectors)
            # ...existing code...
            try:
                details["url"] = self.driver.current_url
                if "/jobs/view/" in details["url"]:
                    details["id"] = details["url"].split("/jobs/view/")[1].split("?")[0]
            except Exception:
                details["url"] = ""
                # ...existing code...
            details["description"] = self._get_job_description()
            details["applicant_count"] = self._parse_applicants()
            details["match_score"] = 0
            # Log if title or company is empty for debugging
            if not details["title"] or not details["company"]:
                self.logger.warning(
                    "    ⚠️ Job details extraction: missing title or company after all selectors."
                )
            return details
        except Exception as exc:
            self.logger.debug(f"Error extracting job details: {exc}")
            return None

    def _get_job_description(self) -> str:
        if self.driver is None:
            return ""
        selectors = [
            "div.show-more-less-html__markup",
            "div.jobs-box__html-content",
            "div.jobs-description__content",
        ]
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.get_attribute("innerText")
                if text:
                    return str(text).strip()
            except Exception:
                continue
        return ""

    def _safe_find_text(self, selector: str) -> str:
        try:
            if self.driver is None:
                return ""
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text.strip()
        except Exception:
            return ""

    def _safe_get(self, url: str, retries: int = 2, delay: float = 2.0) -> bool:
        from utils.webdriver_utils import safe_get

        return safe_get(self.driver, self.logger, url, retries, delay)

    def _safe_find_text_multi(self, selectors: list[str]) -> str:
        if self.driver is None:
            return ""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _parse_applicants(self) -> int:
        if self.driver is None:
            return 0
        selectors = [
            "span.jobs-premium-applicant-insights__list-num",
            "li.jobs-premium-applicant-insights__list-item",
            "span.jobs-unified-top-card__applicant-count",
            "span.jobs-unified-top-card__applicants-text",
            "span.jobs-unified-top-card__bullet",
            "span.jobs-unified-top-card__subtitle-secondary-grouping",
            "span.jobs-unified-top-card__subtitle-primary-grouping",
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.lower()
                    match = re.search(r"([\d,]+)\+?\s*(?:applicants?|total)", text)
                    if match:
                        digits = match.group(1).replace(",", "")
                        return int(digits)
                    # Handles cases where the element is just a number inside applicant insights
                    just_num = re.search(r"^[\d,]+$", text.strip())
                    if just_num:
                        return int(just_num.group(0).replace(",", ""))
            except Exception:
                continue
        return 0

    def _is_viewed_from_details(self) -> bool:
        if self.driver is None:
            return False
        selectors = ["span.jobs-unified-top-card__application-link--viewed"]
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if "viewed" in element.text.lower():
                    return True
            except Exception:
                continue
        return False

    def _check_visa_sponsorship(self, description: str) -> bool:
        return self._sponsors_visa(description, title="", company="")

    def _safe_click(self, selector: str):
        try:
            if self.wait is None or self.driver is None:
                return False
            element = self.wait.until(
                expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
            return True
        except Exception:
            return False

    def _scroll_element(self, selector: str):
        try:
            if self.driver is None:
                return False
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", element
            )
            return True
        except Exception:
            return False

    def _save_job(self):
        try:
            if self.driver is None:
                return False
            selectors = ["button.jobs-save-button", "button.jobs-save-button--save"]
            for selector in selectors:
                try:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    button.click()
                    time.sleep(1)
                    return True
                except Exception:
                    continue
        except Exception as exc:
            self.logger.debug(f"Could not save job: {exc}")
        return False

    def _safe_back(self, retries: int = 3):
        if self.driver is None:
            return
        for _ in range(retries):
            try:
                self.driver.back()
                time.sleep(1)
                return
            except Exception:
                time.sleep(1)
                continue

    def _detect_job_card(self, container, text: str) -> bool:
        try:
            return text.lower() in container.text.lower()
        except Exception:
            return False
