"""
LinkedIn job detail scraper
Scrapes detailed job information from the right-pane job view
"""

import random
import re
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


class JobDetailScraper:
    """Scrapes detailed job information from LinkedIn job view (right pane)"""

    def __init__(self, driver: WebDriver, config):
        """
        Initialize job detail scraper.

        Args:
            driver: Selenium WebDriver instance
            config: Configuration object with scraping settings
        """
        self.driver = driver
        self.config = config
        self.wait = WebDriverWait(driver, 10)

    def scrape_job_details(
        self, job_id: str, max_retries: int = 3
    ) -> dict[str, Any] | None:
        """
        Scrape detailed information for a specific job.

        Args:
            job_id: LinkedIn job ID
            max_retries: Maximum number of retry attempts on failure

        Returns:
            Job details dictionary with keys:
                - job_id: LinkedIn job ID
                - job_url: Full LinkedIn job URL
                - description: Full job description text
                - seniority: Seniority level (e.g., "Entry level", "Mid-Senior level")
                - employment_type: Employment type (e.g., "Full-time", "Contract")
                - job_function: Job function (e.g., "Engineering", "Information Technology")
                - industries: Company industries
                - posted_time: When the job was posted (e.g., "2 days ago")
                - applicant_count: Number of applicants (if available)
                - remote_eligible: Whether the job is remote-eligible
            Returns None if scraping fails after retries
        """
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"[JOB_DETAIL] Scraping job details for ID {job_id} (attempt {attempt + 1}/{max_retries})"
                )

                # Click the job card to load details in right pane
                self._click_job_card(job_id)
                self._random_delay(min_delay=1, max_delay=3)

                # Wait for job details to load
                try:
                    self.wait.until(
                        EC.presence_of_element_located(
                            (By.CLASS_NAME, "jobs-search__job-details")
                        )
                    )
                except TimeoutException:
                    logger.warning(
                        f"[JOB_DETAIL] Job details panel did not load for ID {job_id}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    return None

                # Extract all job details
                details = self._extract_job_details(job_id)

                if details:
                    logger.info(f"[JOB_DETAIL] Successfully scraped job ID {job_id}")
                    return details
                else:
                    logger.warning(
                        f"[JOB_DETAIL] Failed to extract details for job ID {job_id}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    return None

            except StaleElementReferenceException:
                logger.warning(
                    f"[JOB_DETAIL] Stale element for job ID {job_id}, retrying..."
                )
                if attempt < max_retries - 1:
                    self._random_delay()
                    continue
                return None

            except Exception as e:
                logger.error(
                    f"[JOB_DETAIL] Error scraping job ID {job_id}: {e}", exc_info=True
                )
                if attempt < max_retries - 1:
                    self._random_delay()
                    continue
                return None

        logger.error(
            f"[JOB_DETAIL] Failed to scrape job ID {job_id} after {max_retries} attempts"
        )
        return None

    def _click_job_card(self, job_id: str):
        """
        Click on a job card to load its details in the right pane.

        Args:
            job_id: LinkedIn job ID
        """
        try:
            # Find job card by job ID
            job_card = self.driver.find_element(
                By.CSS_SELECTOR, f"a[href*='/jobs/view/{job_id}']"
            )

            # Scroll to the job card
            self.driver.execute_script("arguments[0].scrollIntoView(true);", job_card)
            time.sleep(0.5)

            # Click the job card
            job_card.click()
            logger.debug(f"[JOB_DETAIL] Clicked job card for ID {job_id}")

        except NoSuchElementException:
            logger.error(f"[JOB_DETAIL] Could not find job card for ID {job_id}")
            raise
        except Exception as e:
            logger.error(f"[JOB_DETAIL] Error clicking job card for ID {job_id}: {e}")
            raise

    def _extract_job_details(self, job_id: str) -> dict[str, Any] | None:
        """
        Extract all details from the job details pane.

        Args:
            job_id: LinkedIn job ID

        Returns:
            Dictionary with job details or None if extraction fails
        """
        try:
            details: dict[str, Any] = {
                "job_id": job_id,
                "job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
            }

            # Extract job description
            try:
                desc_elem = self.driver.find_element(
                    By.CLASS_NAME, "jobs-description__content"
                )
                # Click "Show more" button if present
                try:
                    show_more_btn = desc_elem.find_element(
                        By.CSS_SELECTOR, "button[aria-label*='more']"
                    )
                    show_more_btn.click()
                    time.sleep(0.5)
                except (NoSuchElementException, Exception):
                    pass  # No "Show more" button or click failed

                details["description"] = desc_elem.text.strip()
            except NoSuchElementException:
                logger.warning(
                    f"[JOB_DETAIL] Could not find description for job ID {job_id}"
                )
                details["description"] = ""

            # Extract job criteria (seniority, employment type, etc.)
            try:
                # Try multiple selectors for job criteria
                criteria_items = []
                for selector in [
                    ".jobs-unified-top-card__job-insight",
                    ".job-details-jobs-unified-top-card__job-insight",
                    ".jobs-unified-top-card__job-insight-view-model-secondary",
                    "span.ui-label",
                ]:
                    try:
                        items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if items:
                            criteria_items.extend(items)
                    except NoSuchElementException:
                        continue

                for item in criteria_items:
                    try:
                        text = item.text.strip()

                        # Parse different criteria types
                        if "Seniority level" in text or "level" in text.lower():
                            details["seniority"] = text.replace(
                                "Seniority level", ""
                            ).strip()
                        elif (
                            "Employment type" in text
                            or "Full-time" in text
                            or "Part-time" in text
                        ):
                            details["employment_type"] = text.replace(
                                "Employment type", ""
                            ).strip()
                        elif "Job function" in text:
                            details["job_function"] = text.replace(
                                "Job function", ""
                            ).strip()
                        elif "Industries" in text:
                            details["industries"] = text.replace(
                                "Industries", ""
                            ).strip()

                    except Exception as e:
                        logger.debug(f"[JOB_DETAIL] Error parsing criteria item: {e}")
                        continue

            except NoSuchElementException:
                logger.debug(
                    f"[JOB_DETAIL] No criteria items found for job ID {job_id}"
                )

            # Extract posted time
            try:
                posted_time = None
                for selector in [
                    ".jobs-unified-top-card__posted-date",
                    ".job-details-jobs-unified-top-card__primary-description",
                    ".jobs-unified-top-card__subtitle",
                    "span.tvm__text--low-emphasis",
                ]:
                    try:
                        posted_elem = self.driver.find_element(
                            By.CSS_SELECTOR, selector
                        )
                        text = posted_elem.text.strip()
                        # Check if text looks like a time indicator
                        if any(
                            keyword in text.lower()
                            for keyword in [
                                "ago",
                                "hours",
                                "days",
                                "weeks",
                                "reposted",
                                "posted",
                            ]
                        ):
                            posted_time = text
                            break
                    except NoSuchElementException:
                        continue
                details["posted_time"] = posted_time or "Unknown"
            except NoSuchElementException:
                details["posted_time"] = "Unknown"

            # Extract applicant count
            try:
                applicant_count = None
                for selector in [
                    ".jobs-unified-top-card__applicant-count",
                    ".jobs-unified-top-card__bullet",
                    "span.tvm__text--low-emphasis",
                    ".job-details-jobs-unified-top-card__primary-description",
                ]:
                    try:
                        applicant_elem = self.driver.find_element(
                            By.CSS_SELECTOR, selector
                        )
                        applicant_text = applicant_elem.text.strip()
                        # Parse number from text like "Be among the first 25 applicants" or "50 applicants"
                        if "applicant" in applicant_text.lower():
                            match = re.search(r"(\d+)", applicant_text)
                            if match:
                                applicant_count = int(match.group(1))
                                break
                    except NoSuchElementException:
                        continue
                details["applicant_count"] = applicant_count
            except NoSuchElementException:
                details["applicant_count"] = None

            # Determine if remote eligible
            # Check job description and criteria for remote indicators
            remote_keywords = ["remote", "work from home", "wfh", "hybrid"]
            description_lower = details.get("description", "").lower()

            details["remote_eligible"] = any(
                keyword in description_lower for keyword in remote_keywords
            )

            # Also check top card for remote badge
            try:
                workplace_type = self.driver.find_element(
                    By.CSS_SELECTOR, ".jobs-unified-top-card__workplace-type"
                )
                workplace_text = workplace_type.text.strip().lower()
                if "remote" in workplace_text or "hybrid" in workplace_text:
                    details["remote_eligible"] = True
            except NoSuchElementException:
                pass

            # Set default values for missing fields
            details.setdefault("seniority", "Unknown")
            details.setdefault("employment_type", "Unknown")
            details.setdefault("job_function", "Unknown")
            details.setdefault("industries", "Unknown")

            logger.debug(
                f"[JOB_DETAIL] Extracted {len(details)} fields for job ID {job_id}"
            )
            return details

        except Exception as e:
            logger.error(
                f"[JOB_DETAIL] Error extracting job details: {e}", exc_info=True
            )
            return None

    def _random_delay(
        self, min_delay: float | None = None, max_delay: float | None = None
    ):
        """
        Add a random delay between requests to avoid rate limiting.

        Args:
            min_delay: Minimum delay in seconds (defaults to config value)
            max_delay: Maximum delay in seconds (defaults to config value)
        """
        min_d = min_delay or self.config.request_delay_min
        max_d = max_delay or self.config.request_delay_max
        delay = random.uniform(min_d, max_d)
        logger.debug(f"[JOB_DETAIL] Waiting {delay:.2f} seconds")
        time.sleep(delay)
