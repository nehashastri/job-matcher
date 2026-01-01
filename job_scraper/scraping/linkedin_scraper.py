"""
LinkedIn job scraper with proper UI handling and 'Viewed' status detection
"""

import json
import logging
import os
import re
import time
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from config.config import get_config
from filtering.blocklist import Blocklist
from matching.hr_checker import HRChecker

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job listings with proper 'Viewed' detection"""

    def __init__(self):
        super().__init__("linkedin")
        self.base_url = "https://www.linkedin.com"
        self.user_email = os.getenv("LINKEDIN_EMAIL", "")
        self.user_password = os.getenv("LINKEDIN_PASSWORD", "")
        self.driver = None
        self.authenticated = False
        self.wait = None

        # Config-driven components
        self.config = get_config()
        self.blocklist = Blocklist(config=self.config, logger=self.logger)
        self.hr_checker = HRChecker(
            config=self.config, blocklist=self.blocklist, logger=self.logger
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

            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 15)
            self.logger.debug("Chrome WebDriver initialized")
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

            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            time.sleep(4)

            try:
                self.wait.until(
                    expected_conditions.presence_of_element_located((By.CLASS_NAME, "global-nav"))
                )
                self.authenticated = True
                self.logger.info(f"✅ Successfully logged in to LinkedIn as {self.user_email}")
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
        connect_limit: int = 5,
        team_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        """Main scraping method with inline scoring/export/connect."""
        self.logger.info("=" * 60)
        self.logger.info("🚀 Starting LinkedIn scraper")
        self.logger.info("=" * 60)

        jobs: list[dict[str, Any]] = []
        queries = ["data scientist", "machine learning engineer", "AI engineer", "ML engineer"]

        try:
            if not self._login():
                self.logger.warning("Cannot proceed without login")
                return jobs

            self.logger.info(f"📋 Scraping {len(queries)} job queries...")

            found_match = False
            for query in queries:
                try:
                    self.logger.info(f"🔎 Searching for: '{query}'")
                    page_jobs, matched = self._scrape_query(
                        query,
                        max_applicants,
                        scorer=scorer,
                        match_threshold=match_threshold,
                        storage=storage,
                        connect_limit=connect_limit,
                        team_hint=team_hint,
                    )
                    self.logger.info(f"✅ Processed {len(page_jobs)} jobs for '{query}'")
                    jobs.extend(page_jobs)
                    if matched:
                        found_match = True
                        break
                except Exception as exc:
                    self.logger.error(f"❌ Error scraping '{query}': {exc}")
            if found_match:
                self.logger.info("🎯 Match found and processed; exiting scrape early")
                self._log_scrape_result(len(jobs))
                return jobs

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
        connect_limit: int = 5,
        team_hint: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Scrape jobs for a single query; return (jobs, matched_flag)."""
        jobs: list[dict[str, Any]] = []
        matched = False
        try:
            search_url = self._build_search_url(query)
            self.logger.debug(f"  Navigating to: {search_url}")
            self.driver.get(search_url)
            try:
                self.wait.until(
                    expected_conditions.presence_of_element_located(
                        (By.CSS_SELECTOR, "ul.scaffold-layout__list, div.jobs-search-results-list")
                    )
                )
            except Exception:
                self.logger.debug("  Job list did not become visible in time")
            time.sleep(3)
            self._scroll_job_list()
            job_cards = self._get_job_cards()
            self.logger.info(f"  📦 Found {len(job_cards)} job cards for '{query}'")
            if not job_cards:
                return jobs, matched
            for idx in range(len(job_cards)):
                try:
                    job_cards = self._get_job_cards()
                    if idx >= len(job_cards):
                        break
                    job_card = job_cards[idx]
                    self.logger.debug(f"  Processing job {idx + 1}/{len(job_cards)}")
                    if self._is_viewed(job_card):
                        self.logger.debug("    ⏭️  Skipped: Already viewed")
                        continue
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", job_card)
                        time.sleep(0.5)
                        try:
                            link = job_card.find_element(
                                By.CSS_SELECTOR, "a.job-card-list__title, a.app-aware-link"
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
                        self.logger.debug("    ❌ Could not extract job details")
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

                    # Blocklist gate
                    if company_name and self.blocklist.is_blocked(company_name):
                        self.logger.info(
                            f"    ❌ Rejected: {company_name} blocked (no downstream processing)"
                        )
                        self._close_extra_tabs()
                        self._safe_back_to_results(search_url)
                        continue

                    # HR check (configurable)
                    hr_result = self.hr_checker.check(company_name, description=description)
                    if hr_result.get("is_hr_company"):
                        self.logger.info(
                            f"    ❌ Rejected: {company_name} flagged as HR/staffing. Reason: {hr_result.get('reason', '')}"
                        )
                        self._close_extra_tabs()
                        self._safe_back_to_results(search_url)
                        continue

                    if not self._check_visa_sponsorship(description):
                        self.logger.info("    ❌ Skipped: Explicitly states no sponsorship")
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
                            job, connect_limit=connect_limit, team_hint=team_hint
                        )
                    except Exception as exc:
                        self.logger.debug(f"    Connection attempts failed: {exc}")
                    self._close_extra_tabs()
                    self._safe_back_to_results(search_url)
                    matched = True
                    return jobs, matched
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
        except Exception as exc:
            self.logger.error(f"  Error in _scrape_query: {exc}")
        return jobs, matched

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
                self.driver.get(search_url)
                time.sleep(2)
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

    def _build_search_url(self, query: str) -> str:
        """Build LinkedIn job search URL with filters"""
        base = f"{self.base_url}/jobs/search/?"
        params = [
            f"keywords={query.replace(' ', '%20')}",
            "location=United%20States",
            "f_TPR=r86400",
            "f_E=1%2C2%2C3",
            "sortBy=DD",
        ]
        return base + "&".join(params)

    def _scroll_job_list(self):
        """Scroll the job list to load more jobs"""
        try:
            job_list_selectors = [
                "div.jobs-search-results-list",
                "div.scaffold-layout__list-container",
                "ul.scaffold-layout__list",
            ]
            for selector in job_list_selectors:
                try:
                    job_list = self.driver.find_element(By.CSS_SELECTOR, selector)
                    for _ in range(3):
                        self.driver.execute_script(
                            "arguments[0].scrollTop = arguments[0].scrollHeight", job_list
                        )
                        time.sleep(1)
                    return
                except Exception:
                    continue
        except Exception as exc:
            self.logger.debug(f"Could not scroll job list: {exc}")

    def _get_job_cards(self) -> list:
        """Get all job card elements"""
        selectors = [
            "li.jobs-search-results__list-item",
            "div.job-card-container",
            "li.scaffold-layout__list-item",
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return elements  # type: ignore[no-any-return]
            except Exception:
                continue
        return []

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
                "h1.job-details-jobs-unified-top-card__job-title a",
                "h1.jobs-unified-top-card__job-title a",
                "h2.t-24",
            ]
            details["title"] = self._safe_find_text_multi(title_selectors)
            company_selectors = [
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
            details["location"] = self._safe_find_text_multi(location_selectors) or "United States"
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
            details["employment_type"] = self._safe_find_text(
                "span.jobs-unified-top-card__workplace-type"
            )
            details["applicant_count"] = self._parse_applicants()
            details["posted_date"] = self._parse_posted_date()
            details["match_score"] = 0
            details["source"] = "LinkedIn"
            details["viewed"] = self._is_viewed_from_details()
            details["via_easy_apply"] = self._has_easy_apply()
            details["company_followers"] = self._parse_company_followers()
            details["benefits"] = self._parse_benefits()
            details["seniority_level"] = self._parse_seniority_level()
            details["company_size"] = self._parse_company_size()
            details["industries"] = self._parse_industries()
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
                    return text.strip()  # type: ignore[no-any-return]
            except Exception:
                continue
        return ""

    def _safe_find_text(self, selector: str) -> str:
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text.strip()  # type: ignore[no-any-return]
        except Exception:
            return ""

    def _safe_find_text_multi(self, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text  # type: ignore[no-any-return]
            except Exception:
                continue
        return ""

    def _parse_applicants(self) -> int:
        selectors = [
            "span.jobs-unified-top-card__applicant-count",
            "span.jobs-unified-top-card__bullet",
            "span.jobs-unified-top-card__subtitle-secondary-grouping",
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.lower()
                    match = re.search(r"(\d+) applicants?", text)
                    if match:
                        return int(match.group(1))
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
                    return text  # type: ignore[no-any-return]
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
                        return [item.text.strip() for item in items if item.text.strip()]
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
                        return text.replace("seniority level", "").strip()  # type: ignore[no-any-return]
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
                        return text.strip()  # type: ignore[no-any-return]
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
                            p.strip() for p in text.replace("industry", "").split(",") if p.strip()
                        ]
                        return parts
            except Exception:
                continue
        return []

    def _check_visa_sponsorship(self, description: str) -> bool:
        return self._sponsors_visa(description, title="", company="")

    def _connect_to_people(self, job: dict, connect_limit: int = 5, team_hint: str | None = None):
        try:
            company = job.get("company", "")
            role = job.get("title", "")
            search_query = f"{company} {role} hiring manager {team_hint or ''} site:linkedin.com/in"
            self.logger.info(f"    🌐 Searching for people: {search_query}")
            if not self._login():
                return
            self.driver.execute_script("window.open('about:blank','_blank');")
            handles = self.driver.window_handles
            self.driver.switch_to.window(handles[-1])
            self.driver.get("https://www.google.com")
            time.sleep(2)
            search_box = self.wait.until(
                expected_conditions.presence_of_element_located((By.NAME, "q"))
            )
            search_box.clear()
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.RETURN)
            time.sleep(2)
            links = self.driver.find_elements(By.CSS_SELECTOR, "a")
            people: list[dict[str, str]] = []
            for link in links[: connect_limit * 2]:
                href = link.get_attribute("href")
                if not href or "linkedin.com/in" not in href:
                    continue
                text = link.text.strip()
                if not text:
                    continue
                title = link.get_attribute("aria-label") or text
                people.append({"name": text, "title": title, "profile_url": href})
                if len(people) >= connect_limit:
                    break
            if people:
                self.logger.info(f"    🔗 Found {len(people)} potential contacts")
                for person in people:
                    self.logger.info(f"      - {person['name']} | {person['profile_url']}")
            else:
                self.logger.info("    No potential contacts found")
            try:
                self.driver.close()
                self.driver.switch_to.window(handles[0])
            except Exception:
                pass
        except Exception as exc:
            self.logger.debug(f"    Could not connect to people: {exc}")

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
        info: dict[str, str | None] = {"company_link": None, "company_description": None}
        try:
            link_elem = self.driver.find_element(By.CSS_SELECTOR, "a.topcard__org-name-link")
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
