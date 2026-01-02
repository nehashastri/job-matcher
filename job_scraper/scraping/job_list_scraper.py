"""
LinkedIn job list scraper
Scrapes job listings from the left-pane search results
"""

import random
import time
from typing import Any

from config.logging_utils import get_logger
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = get_logger(__name__)


class JobListScraper:
    """Scrapes job listings from LinkedIn search results (left pane)"""

    def __init__(self, driver: WebDriver, config):
        """
        Initialize job list scraper.

        Args:
            driver: Selenium WebDriver instance
            config: Configuration object with scraping settings
        """
        self.driver = driver
        self.config = config
        self.wait = WebDriverWait(driver, 10)

    def scrape_job_list(
        self, search_url: str, max_jobs: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Scrape job listings from a LinkedIn search results page.

        Args:
            search_url: LinkedIn job search URL
            max_jobs: Maximum number of jobs to scrape (None for all)

        Returns:
            List of job dictionaries with keys:
                - job_id: LinkedIn job ID
                - title: Job title
                - company: Company name
                - location: Job location
                - is_viewed: Whether the job has been viewed (based on visual indicator)
        """
        logger.info(f"[SCRAPE_LIST] Starting job list scrape: {search_url}")

        # Navigate to search URL
        self.driver.get(search_url)
        self._random_delay()

        # Wait for job list to load
        # Try multiple possible selectors as LinkedIn structure varies
        list_loaded = False
        for selector in ["scaffold-layout__list", "jobs-search__results-list"]:
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, selector))
                )
                logger.debug(
                    f"[SCRAPE_LIST] Job list loaded using selector: {selector}"
                )
                list_loaded = True
                break
            except TimeoutException:
                continue

        if not list_loaded:
            logger.warning("[SCRAPE_LIST] Job list did not load within timeout")
            return []

        jobs = []
        max_jobs = max_jobs or self.config.max_jobs_per_role

        # Scroll and load jobs until we have enough
        page_num = 0
        while len(jobs) < max_jobs:
            # Scrape current page
            new_jobs = self._scrape_current_page()

            if not new_jobs:
                logger.info(f"[SCRAPE_LIST] No more jobs found on page {page_num}")
                break

            jobs.extend(new_jobs)
            logger.info(
                f"[SCRAPE_LIST] Page {page_num}: scraped {len(new_jobs)} jobs (total: {len(jobs)})"
            )

            # Check if we have enough jobs
            if len(jobs) >= max_jobs:
                jobs = jobs[:max_jobs]
                break

            # Try to load more jobs by scrolling
            if not self._scroll_to_load_more():
                logger.info("[SCRAPE_LIST] Reached end of job list")
                break

            page_num += 1
            self._random_delay()

        # Filter to unviewed jobs if configured
        if self.config.skip_viewed_jobs:
            unviewed_jobs = [job for job in jobs if not job.get("is_viewed", False)]
            logger.info(
                f"[SCRAPE_LIST] Filtered to {len(unviewed_jobs)} unviewed jobs (out of {len(jobs)})"
            )
            return unviewed_jobs

        return jobs

    def _scrape_current_page(self) -> list[dict[str, Any]]:
        """
        Scrape all job cards currently visible on the page.

        Returns:
            List of job dictionaries
        """
        jobs = []

        try:
            # Find all job card elements - try multiple selectors
            job_cards = []

            # Try new LinkedIn structure first (as of late 2024/2025)
            job_cards = self.driver.find_elements(By.CLASS_NAME, "job-card-container")

            # Fallback to old structure
            if not job_cards:
                job_cards = self.driver.find_elements(
                    By.CSS_SELECTOR, "ul.jobs-search__results-list > li"
                )

            logger.debug(f"[SCRAPE_LIST] Found {len(job_cards)} job card elements")

            for card in job_cards:
                try:
                    job = self._extract_job_from_card(card)
                    if job:
                        jobs.append(job)
                    else:
                        logger.debug("[SCRAPE_LIST] Job extraction returned None")
                except StaleElementReferenceException:
                    logger.warning(
                        "[SCRAPE_LIST] Stale element encountered, skipping job"
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"[SCRAPE_LIST] Error extracting job from card: {e}",
                        exc_info=True,
                    )
                    continue

        except Exception as e:
            logger.error(f"[SCRAPE_LIST] Error finding job cards: {e}")

        return jobs

    def _extract_job_from_card(self, card) -> dict[str, Any] | None:
        """
        Extract job information from a job card element.

        Args:
            card: Selenium WebElement representing a job card

        Returns:
            Job dictionary or None if extraction fails
        """
        try:
            # Extract job ID - try data attribute first (new LinkedIn structure)
            job_id = card.get_attribute("data-job-id")

            # Extract job link
            job_link = None
            for selector in [
                "a",  # Simple anchor tag works in new structure
                "a.job-card-list__title",
                "a[data-job-id]",
                "a.job-card-container__link",
                "a[href*='/jobs/view/']",
            ]:
                try:
                    job_link = card.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if not job_link:
                logger.warning("[SCRAPE_LIST] Could not find job link in card")
                return None

            job_url = job_link.get_attribute("href")

            # If we didn't get job_id from data attribute, extract from URL
            if not job_id and "/jobs/view/" in job_url:
                job_id = job_url.split("/jobs/view/")[1].split("/")[0].split("?")[0]

            if not job_id:
                logger.warning("[SCRAPE_LIST] Could not extract job ID")
                return None

            # Extract job title
            title = job_link.text.strip()
            if not title:
                # Try to find title in nested elements
                try:
                    title_elem = job_link.find_element(By.CSS_SELECTOR, "[aria-label]")
                    title = title_elem.get_attribute("aria-label")
                except NoSuchElementException:
                    title = "Unknown"

            # Extract company name
            company = "Unknown"
            for selector in [
                ".job-card-container__company-name",
                ".artdeco-entity-lockup__subtitle",
                ".job-card-container__primary-description",
            ]:
                try:
                    company_elem = card.find_element(By.CSS_SELECTOR, selector)
                    company = company_elem.text.strip()
                    if company:  # Make sure it's not empty
                        break
                except NoSuchElementException:
                    continue

            # Extract location
            location = "Unknown"
            for selector in [
                ".job-card-container__metadata-item",
                ".artdeco-entity-lockup__caption",
                ".job-card-container__metadata-wrapper",
            ]:
                try:
                    location_elem = card.find_element(By.CSS_SELECTOR, selector)
                    location = location_elem.text.strip()
                    if location:  # Make sure it's not empty
                        break
                except NoSuchElementException:
                    continue

            # Determine if job has been viewed
            # LinkedIn toggles several possible classes/flags for viewed cards
            is_viewed = False
            viewed_indicator = None
            try:
                card_classes = card.get_attribute("class") or ""
                link_classes = job_link.get_attribute("class") or ""

                # Class-based signals
                visited_classes = [
                    "job-card-container--visited",
                    "job-card-list--visited",
                    "job-card-container--is-viewed",
                    "is-dismissed",
                    "visited",
                    "seen",
                ]
                for marker in visited_classes:
                    if marker in card_classes or marker in link_classes:
                        is_viewed = True
                        viewed_indicator = f"has '{marker}' class"
                        break

                # Data attributes sometimes toggle when viewed
                if not is_viewed:
                    data_viewed = card.get_attribute(
                        "data-viewed"
                    ) or job_link.get_attribute("data-viewed")
                    if data_viewed and data_viewed.lower() in ["true", "1", "yes"]:
                        is_viewed = True
                        viewed_indicator = "data-viewed=true"

                # Visible text marker (LinkedIn shows a "Viewed" label on cards)
                if not is_viewed:
                    card_text = (card.text or "").lower()
                    if "viewed" in card_text:
                        is_viewed = True
                        viewed_indicator = "text contains 'viewed'"

                # Log what we found for debugging
                if is_viewed:
                    logger.debug(
                        f"[SCRAPE_LIST] Job {job_id} marked as VIEWED ({viewed_indicator})"
                    )
            except Exception as e:
                logger.debug(
                    f"[SCRAPE_LIST] Could not determine viewed status for job {job_id}: {e}"
                )

            job = {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "is_viewed": is_viewed,
                "viewed_indicator": viewed_indicator,
                "job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
            }

            logger.debug(
                f"[SCRAPE_LIST] Extracted job: {title} at {company} (ID: {job_id}, viewed={is_viewed})"
            )
            return job

        except NoSuchElementException as e:
            logger.warning(f"[SCRAPE_LIST] Missing element in job card: {e}")
            return None
        except Exception as e:
            logger.error(f"[SCRAPE_LIST] Error extracting job: {e}")
            return None

    def _scroll_to_load_more(self) -> bool:
        """
        Scroll down to load more jobs.

        Returns:
            True if more jobs were loaded, False if at end
        """
        try:
            # Get current job count
            current_count = len(
                self.driver.find_elements(
                    By.CSS_SELECTOR, "ul.jobs-search__results-list > li"
                )
            )

            # Scroll to bottom of job list
            job_list = self.driver.find_element(
                By.CLASS_NAME, "jobs-search__results-list"
            )
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", job_list
            )

            # Wait a bit for new jobs to load
            time.sleep(2)

            # Check if new jobs were loaded
            new_count = len(
                self.driver.find_elements(
                    By.CSS_SELECTOR, "ul.jobs-search__results-list > li"
                )
            )

            return new_count > current_count

        except Exception as e:
            logger.error(f"[SCRAPE_LIST] Error scrolling to load more: {e}")
            return False

    def _random_delay(self):
        """Add a random delay between requests to avoid rate limiting"""
        delay = random.uniform(
            self.config.request_delay_min, self.config.request_delay_max
        )
        logger.debug(f"[SCRAPE_LIST] Waiting {delay:.2f} seconds")
        time.sleep(delay)
