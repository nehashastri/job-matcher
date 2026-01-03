"""
LinkedIn job scraper with proper UI handling and 'Viewed' status detection
"""

import json
import logging
import math
import os
import re
import time
from typing import Any, cast

from config.config import get_config
from filtering.blocklist import Blocklist
from matching.hr_checker import HRChecker
from matching.sponsorship_filter import SponsorshipFilter
from networking.connection_requester import ConnectionRequester
from networking.people_finder import PeopleFinder
from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job listings with proper 'Viewed' detection"""

    def __init__(self):
        super().__init__("linkedin")
        self.base_url = "https://www.linkedin.com"
        self.user_email = os.getenv("LINKEDIN_EMAIL", "")
        self.user_password = os.getenv("LINKEDIN_PASSWORD", "")
        self.driver = cast(webdriver.Chrome, None)
        self.authenticated = False
        self.wait = cast(WebDriverWait, None)

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

            if self.config.headless:
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")

            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 15)
            self.logger.debug("Chrome WebDriver initialized (fresh profile)")
        except Exception as exc:
            self.logger.error(f"Failed to initialize WebDriver: {exc}")
            raise

    def _login(self) -> bool:
        """Login to LinkedIn"""
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
        team_hint: str | None = None,
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

        queries = [
            role.get("title", "").strip()
            for role in configured_roles
            if role.get("enabled", True) and role.get("title")
        ]
        queries = [q for i, q in enumerate(queries) if q and q not in queries[:i]]

        if not queries:
            self.logger.warning(
                "No enabled roles found in roles.json; skipping LinkedIn scrape."
            )
            return jobs

        try:
            if not self._login():
                self.logger.warning("Cannot proceed without login")
                return jobs

            self.logger.info(f"📋 Scraping {len(queries)} job queries...")

            for query in queries:
                try:
                    self.logger.info(f"🔎 Searching for: '{query}'")
                    page_jobs, matched = self._scrape_query(
                        query,
                        max_applicants,
                        scorer=scorer,
                        match_threshold=match_threshold,
                        storage=storage,
                        connect_pages=connect_pages,
                        connect_delay_range=connect_delay_range,
                        team_hint=team_hint,
                        max_pages=8,
                    )
                    self.logger.info(
                        f"✅ Processed {len(page_jobs)} jobs for '{query}'"
                    )
                    jobs.extend(page_jobs)
                except Exception as exc:
                    self.logger.error(f"❌ Error scraping '{query}': {exc}")

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

    def _scrape_query(
        self,
        query: str,
        max_applicants: int,
        scorer=None,
        match_threshold: float = 0.0,
        storage=None,
        connect_pages: int | None = 3,
        connect_delay_range: tuple[float, float] = (1.0, 2.0),
        team_hint: str | None = None,
        max_pages: int = 8,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Scrape jobs for a single query; up to max_pages; return (jobs, matched_flag)."""

        jobs: list[dict[str, Any]] = []
        matched = False
        total_pages: int | None = None
        current_page = 1

        try:
            search_url = self._build_search_url(query, start=0)
            self.logger.info("=" * 60)
            self.logger.info(f"  📄 Page 1/{max_pages} for '{query}' (start=0)")
            self.logger.debug(f"  Navigating to: {search_url}")
            if not self._safe_get(search_url):
                self.logger.error("  Could not navigate to search URL; aborting query")
                return jobs, matched

            while current_page <= max_pages:
                page_state = self._get_page_state()
                if page_state:
                    if page_state[0]:
                        current_page = page_state[0]
                    if total_pages is None and page_state[1]:
                        total_pages = min(max_pages, page_state[1])

                if total_pages is None:
                    total_results = self._get_total_results()
                    if total_results:
                        computed_pages = math.ceil(total_results / 25)
                        total_pages = min(max_pages, computed_pages)
                        self.logger.info(
                            f"  ℹ️ Total results={total_results}; pages={computed_pages}; processing up to {total_pages}"
                        )

                is_last_page = total_pages is not None and current_page >= total_pages
                search_url = self.driver.current_url
                start = (current_page - 1) * 25
                self.logger.info("=" * 60)
                self.logger.info(
                    f"  📄 Page {current_page}/{total_pages or max_pages} for '{query}' (start={start})"
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

                time.sleep(3)
                self._scroll_job_list(target_count=25)
                job_cards = self._get_job_cards(target_count=25)

                if len(job_cards) < 25 and not is_last_page:
                    self.logger.info(
                        f"  ⚠️ Only {len(job_cards)} job cards loaded; forcing more scrolls"
                    )
                    for _ in range(3):
                        self._scroll_job_list(target_count=25)
                        time.sleep(1)
                        job_cards = self._get_job_cards(target_count=25)
                        if len(job_cards) >= 25:
                            break

                if len(job_cards) < 25 and not is_last_page:
                    self.logger.warning(
                        f"  ❌ Expected 25 job cards on non-last page {current_page} but got {len(job_cards)}; skipping page to stay aligned"
                    )
                    if not self._go_to_next_page():
                        break
                    current_page += 1
                    continue

                self.logger.info(
                    f"  📦 Found {len(job_cards)} job cards for '{query}' on page {current_page}"
                )
                if not job_cards:
                    if is_last_page:
                        break
                    if not self._go_to_next_page():
                        break
                    current_page += 1
                    continue

                for idx in range(len(job_cards)):
                    try:
                        self.logger.info("=" * 60)
                        job_cards = self._get_job_cards()
                        if idx >= len(job_cards):
                            break
                        job_card = job_cards[idx]
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
                            time.sleep(2)
                            self._scroll_right_panel()
                            time.sleep(1)
                            self._open_full_job_page()
                            time.sleep(2)
                        except Exception as exc:
                            self.logger.debug(f"    Could not click job card: {exc}")
                            continue
                        job = self._extract_job_details()
                        if not job:
                            self.logger.info(
                                "    ❌ Skipped: Could not extract job details from card"
                            )
                            self._close_extra_tabs()
                            self._safe_back_to_results(search_url)
                            continue
                        self.logger.info(
                            f"    [SCRAPED JOB] {json.dumps(job, ensure_ascii=False, indent=2)}"
                        )
                        company_name = (job.get("company") or "").strip()
                        applicants = job.get("applicant_count", 0)
                        if applicants > max_applicants:
                            self.logger.info(
                                f"    ❌ Skipped: Too many applicants ({applicants} > {max_applicants})"
                            )
                            self._close_extra_tabs()
                            self._safe_back_to_results(search_url)
                            continue
                        description = job.get("description", "")

                        if company_name and self.blocklist.is_blocked(company_name):
                            self.logger.info(
                                f"    ❌ Rejected: {company_name} blocked (no downstream processing)"
                            )
                            self._close_extra_tabs()
                            self._safe_back_to_results(search_url)
                            continue

                        hr_result = self.hr_checker.check(
                            company_name, description=description
                        )
                        if hr_result.get("is_hr_company"):
                            self.logger.info(
                                f"    ❌ Rejected: {company_name} flagged as HR/staffing. Reason: {hr_result.get('reason', '')}"
                            )
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
                                score = float(scorer(job))
                            except Exception as exc:
                                self.logger.error(f"    LLM scoring failed: {exc}")
                                score = 0.0
                            job["match_score"] = score
                            reason = self._short_reason(job.get("match_reason", ""))
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
                            try:
                                storage.export_to_excel()
                            except Exception as exc:
                                self.logger.debug(f"    Excel export failed: {exc}")
                        jobs.append(job)
                        try:
                            self._connect_to_people(
                                job,
                                connect_pages=connect_pages,
                                delay_range=connect_delay_range,
                                storage=storage,
                                team_hint=team_hint,
                            )
                        except Exception as exc:
                            self.logger.debug(f"    Connection attempts failed: {exc}")
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

                if is_last_page:
                    break

                if total_pages is not None and current_page >= total_pages:
                    break

                if current_page >= max_pages:
                    break

                if not self._go_to_next_page():
                    break

                current_page += 1

            if not matched:
                self.logger.info(
                    f"  No matches yet after page {current_page}/{total_pages or max_pages} for '{query}'"
                )

        except Exception as exc:
            self.logger.error(f"  Error in _scrape_query: {exc}")
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
        """Scroll the right job details panel to the bottom to load all content."""
        try:
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
            self.driver.back()
            time.sleep(2)
        except Exception:
            try:
                self._safe_get(search_url)
            except Exception:
                self.logger.debug("Could not navigate back to results")

    def _open_full_job_page(self) -> None:
        """From the right pane, click the job title to open the full page; handle new tab."""
        original_window = self.driver.current_window_handle
        try:
            title_selectors = [
                "a.top-card-layout__title",
                "a.job-details-jobs-unified-top-card__job-title",
                "a.jobs-unified-top-card__job-title",
                "a.job-card-list__title",
            ]
            link = None
            for selector in title_selectors:
                try:
                    link = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if link:
                        break
                except Exception:
                    continue
            if not link:
                self.logger.debug("    Could not find job title link to open full page")
                return
            link_href = link.get_attribute("href")
            self.logger.debug(f"    Opening full job page: {link_href}")
            link.click()
            time.sleep(2)
            handles = self.driver.window_handles
            if len(handles) > 1:
                self.driver.switch_to.window(handles[-1])
        except Exception as exc:
            self.logger.debug(f"    Could not open full job page: {exc}")
            try:
                self.driver.switch_to.window(original_window)
            except Exception:
                pass

    def _close_extra_tabs(self):
        """Close all tabs except the first/main one."""
        try:
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

    def _build_search_url(self, query: str, start: int = 0) -> str:
        """Build LinkedIn job search URL with filters and pagination offset"""
        base = f"{self.base_url}/jobs/search/?"
        params = [
            f"keywords={query.replace(' ', '%20')}",
            "location=United%20States",
            "f_TPR=r86400",
            "f_E=1%2C2%2C3",
            "sortBy=DD",
            f"start={start}",
        ]
        return base + "&".join(params)

    def _scroll_job_list(self, target_count: int = 25):
        """Scroll the job list to load up to target_count cards with extra retries."""

        try:
            selectors = [
                "div.jobs-search-results-list",
                "div.scaffold-layout__list-container",
                "ul.scaffold-layout__list",
                "[data-search-results-container]",
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

            for _ in range(20):
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

                time.sleep(0.9)
                self._wait_for_results_loader()
                new_count = len(self._get_job_cards(target_count=target_count))

                if new_count <= last_count:
                    stagnant_rounds += 1
                    try:
                        self.driver.execute_script("window.scrollBy(0, 800);")
                    except Exception:
                        pass
                    time.sleep(0.4)
                    new_count = len(self._get_job_cards(target_count=target_count))
                else:
                    stagnant_rounds = 0

                if new_count == last_count and stagnant_rounds >= 3:
                    # Likely no more items to load
                    break

                last_count = new_count
        except Exception as exc:
            self.logger.debug(f"Could not scroll job list: {exc}")

    def _wait_for_results_loader(self):
        """Best-effort wait for the results loader to clear after scrolling."""
        try:
            loader_selector = "div.jobs-search-results-list__loader"
            for _ in range(3):
                loaders = self.driver.find_elements(By.CSS_SELECTOR, loader_selector)
                active = any(loader.is_displayed() for loader in loaders)
                if not active:
                    break
                time.sleep(0.3)
        except Exception:
            # Non-fatal; continue without blocking
            pass

    def _get_page_state(self) -> tuple[int | None, int | None]:
        """Return (current_page, total_pages) from the pagination state element."""

        selectors = [
            "p.jobs-search-pagination__page-state",
            "div.jobs-search-pagination__page-state",
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

                match = re.search(r"page\s+(\d+)\s+of\s+(\d+)", text)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    return current, total
        except Exception as exc:
            self.logger.debug(f"Could not parse page state: {exc}")

        return None, None

    def _get_total_results(self) -> int:
        """Parse the total results count from the subtitle element."""

        selectors = [
            "div.jobs-search-results-list__subtitle span",
            "div.jobs-search-results-list__subtitle",
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
        except Exception as exc:
            self.logger.debug(f"Could not parse total results: {exc}")

        return 0

    def _go_to_next_page(self) -> bool:
        """Click the next-page button; return True if navigation was attempted."""

        selectors = [
            "button.jobs-search-pagination__button--next",
            "button[aria-label='View next page']",
        ]

        for selector in selectors:
            try:
                button = self.wait.until(
                    expected_conditions.element_to_be_clickable(
                        (By.CSS_SELECTOR, selector)
                    )
                )
                button.click()
                time.sleep(2)
                return True
            except Exception:
                continue

        self.logger.debug("Could not click next-page button")
        return False

    def _get_job_cards(self, target_count: int = 25) -> list:
        """Collect up to target_count unique, visible job card elements."""

        selectors = [
            "[data-job-id]",
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
        """Extract job details from the job details panel"""
        try:
            details: dict[str, Any] = {}
            title_selectors = [
                "div.job-details-jobs-unified-top-card__job-title h1 a",
                "h1.job-details-jobs-unified-top-card__job-title a",
                "h1.jobs-unified-top-card__job-title a",
                "h1.t-24.t-bold.inline a",
                "h2.t-24",
            ]
            details["title"] = self._safe_find_text_multi(title_selectors)
            company_selectors = [
                "div.job-details-jobs-unified-top-card__company-name a",
                "a.job-details-jobs-unified-top-card__company-name",
                "a.jobs-unified-top-card__company-name",
                "span.jobs-unified-top-card__company-name",
            ]
            details["company"] = self._safe_find_text_multi(company_selectors)
            location_selectors = [
                "span.jobs-unified-top-card__location",
                "span.job-details-jobs-unified-top-card__location",
                "span.jobs-unified-top-card__bullet",
            ]
            details["location"] = (
                self._safe_find_text_multi(location_selectors) or "United States"
            )
            try:
                details["url"] = self.driver.current_url
                if "/jobs/view/" in details["url"]:
                    details["id"] = details["url"].split("/jobs/view/")[1].split("?")[0]
                else:
                    details["id"] = str(hash(details["url"]))
            except Exception:
                details["url"] = ""
                details["id"] = ""
            details["description"] = self._get_job_description()
            details["applicant_count"] = self._parse_applicants()
            details["posted_date"] = self._parse_posted_date()
            details["match_score"] = 0
            details["source"] = "LinkedIn"
            return details
        except Exception as exc:
            self.logger.debug(f"Error extracting job details: {exc}")
            return None

    def _get_job_description(self) -> str:
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
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text.strip()
        except Exception:
            return ""

    def _safe_get(self, url: str, retries: int = 2, delay: float = 2.0) -> bool:
        """Navigate to a URL with lightweight retries to reduce flakiness in headless runs."""
        for attempt in range(retries):
            try:
                self.driver.get(url)
                return True
            except Exception as exc:
                self.logger.debug(
                    f"Nav attempt {attempt + 1}/{retries} failed for {url}: {exc}"
                )
                time.sleep(delay)
        return False

    def _safe_find_text_multi(self, selectors: list[str]) -> str:
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

    def _parse_posted_date(self) -> str:
        selectors = [
            "span.jobs-unified-top-card__posted-date",
            "span.jobs-unified-top-card__subtitle-primary-grouping",
        ]
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _is_viewed_from_details(self) -> bool:
        selectors = ["span.jobs-unified-top-card__application-link--viewed"]
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if "viewed" in element.text.lower():
                    return True
            except Exception:
                continue
        return False

    def _has_easy_apply(self) -> bool:
        selectors = ["button.jobs-apply-button--top-card"]
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.lower()
                if "easy apply" in text:
                    return True
            except Exception:
                continue
        return False

    def _parse_company_followers(self) -> int | None:
        selectors = ["a.topcard__org-name-link"]
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                title = element.get_attribute("title")
                match = re.search(r"([0-9,]+) followers", title or "")
                if match:
                    return int(match.group(1).replace(",", ""))
            except Exception:
                continue
        return None

    def _parse_benefits(self) -> list[str]:
        selectors = ["ul.core-section-container__content"]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if "benefit" in elem.text.lower():
                        items = elem.find_elements(By.TAG_NAME, "li")
                        return [
                            item.text.strip() for item in items if item.text.strip()
                        ]
            except Exception:
                continue
        return []

    def _parse_seniority_level(self) -> str:
        selectors = ["li.jobs-unified-top-card__job-insight"]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.lower()
                    if "seniority level" in text:
                        return text.replace("seniority level", "").strip()
            except Exception:
                continue
        return ""

    def _parse_company_size(self) -> str:
        selectors = ["li.jobs-unified-top-card__job-insight"]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.lower()
                    if "employees" in text:
                        return text.strip()
            except Exception:
                continue
        return ""

    def _parse_industries(self) -> list[str]:
        selectors = ["li.jobs-unified-top-card__job-insight"]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.lower()
                    if "industry" in text:
                        parts = [
                            p.strip()
                            for p in text.replace("industry", "").split(",")
                            if p.strip()
                        ]
                        return parts
            except Exception:
                continue
        return []

    def _check_visa_sponsorship(self, description: str) -> bool:
        return self._sponsors_visa(description, title="", company="")

    def _connect_to_people(
        self,
        job: dict,
        connect_pages: int | None = None,
        delay_range: tuple[float, float] = (1.0, 2.0),
        storage=None,
        team_hint: str | None = None,
    ):
        try:
            company = job.get("company", "")
            role = job.get("title", "")
            if team_hint:
                role = f"{role} {team_hint}".strip()

            if not company or not role:
                self.logger.info(
                    "    [PEOPLE_SEARCH] Missing company or role; skipping networking"
                )
                return

            if not self._login():
                return

            people_finder = PeopleFinder(self.driver, self.wait, self.logger)
            connection_requester = ConnectionRequester(
                self.driver, self.wait, self.logger
            )

            pages = connect_pages if connect_pages is not None else 3

            summary = connection_requester.run_on_people_search(
                people_finder,
                role=role,
                company=company,
                delay_range=delay_range,
                store=storage,
                max_pages=pages,
                use_new_tab=self.config.networking_allow_new_tab,
            )
            self.logger.info(
                "    [CONNECT] Requests: "
                f"message_available={summary['message_available']} connect_match={summary['connect_clicked_match']} "
                f"connect_non_match={summary['connect_clicked_non_match']} skipped={summary['skipped']} "
                f"failed={summary['failed']} pages={summary['pages_processed']}"
            )
            if summary.get("pages_processed", 0) < pages:
                self.logger.info(
                    f"    [CONNECT] Stopped after {summary.get('pages_processed', 0)} page(s); target was {pages}."
                )
        except Exception as exc:
            self.logger.debug(f"    Could not connect to people: {exc}")
        finally:
            # Stay in the current tab; no new tab was opened
            pass

    def _safe_click(self, selector: str):
        try:
            element = self.wait.until(
                expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
            return True
        except Exception:
            return False

    def _scroll_element(self, selector: str):
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", element
            )
            return True
        except Exception:
            return False

    def _save_job(self):
        try:
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

    def _get_people_also_viewed(self) -> list[str]:
        selectors = ["a.job-view-layout__companies-list"]
        profiles: list[str] = []
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selectors[0])
            for element in elements:
                href = element.get_attribute("href")
                if href and "linkedin.com/company" in href:
                    profiles.append(href)
        except Exception as exc:
            self.logger.debug(f"Could not get people-also-viewed: {exc}")
        return profiles

    def _parse_company_info(self) -> dict:
        info: dict[str, str | None] = {
            "company_link": None,
            "company_description": None,
        }
        try:
            link_elem = self.driver.find_element(
                By.CSS_SELECTOR, "a.topcard__org-name-link"
            )
            info["company_link"] = link_elem.get_attribute("href")
        except Exception:
            info["company_link"] = None
        try:
            desc_elem = self.driver.find_element(
                By.CSS_SELECTOR, "div.jobs-company__box .jobs-box__html-content"
            )
            info["company_description"] = desc_elem.text.strip()
        except Exception:
            info["company_description"] = None
        return info

    def _safe_back(self, retries: int = 3):
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

    # --- Job filtering helpers ---
    def _is_relevant_job(self, job: dict) -> bool:
        try:
            location = job.get("location", "") or ""
            description = job.get("description", "") or ""
            title = job.get("title", "") or ""

            if "intern" in title.lower():
                return False
            if not self._is_us_location(location):
                return False
            if not self._check_visa_sponsorship(description):
                return False
            if not self._is_posted_last_24_hours(job.get("posted_date", "")):
                return False
            return True
        except Exception as exc:
            self.logger.debug(f"Job relevance check failed: {exc}")
            return False
