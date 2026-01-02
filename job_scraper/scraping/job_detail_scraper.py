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

from job_scraper.models import JobDetails

logger = get_logger(__name__)


class JobDetailScraper:
    """Scrapes detailed job information from LinkedIn job view (right pane)"""

    def __init__(self, driver: WebDriver, config):
        self.driver = driver
        self.config = config
        self.wait = WebDriverWait(driver, 10)

    def scrape_job_details(
        self, job_id: str, max_retries: int = 3
    ) -> dict[str, Any] | None:
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"[JOB_DETAIL] Scraping job details for ID {job_id} (attempt {attempt + 1}/{max_retries})"
                )

                self._click_job_card(job_id)
                self._random_delay(min_delay=1, max_delay=3)

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

                details = self._extract_job_details(job_id)
                if details:
                    logger.info(f"[JOB_DETAIL] Successfully scraped job ID {job_id}")
                    return details

                logger.warning(
                    f"[JOB_DETAIL] Failed to extract details for job ID {job_id}"
                )
                if attempt < max_retries - 1:
                    continue
                return None

            except StaleElementReferenceException:
                logger.warning(
                    f"[JOB_DETAIL] Stale element while scraping {job_id}; retrying"
                )
                self._random_delay()
                continue
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

    def _click_job_card(self, job_id: str) -> None:
        try:
            job_card = None
            selectors = [
                f"a[data-job-id='{job_id}']",
                f"a[href*='/jobs/view/{job_id}']",
                "a.job-card-container__link",
                "a.job-card-list__title",
            ]
            for selector in selectors:
                try:
                    job_card = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if job_card:
                        break
                except NoSuchElementException:
                    continue

            if not job_card:
                raise NoSuchElementException(f"Job card not found for ID {job_id}")

            self.driver.execute_script("arguments[0].scrollIntoView(true);", job_card)
            time.sleep(0.5)
            job_card.click()
            logger.debug(f"[JOB_DETAIL] Clicked job card for ID {job_id}")

        except Exception:
            logger.error(f"[JOB_DETAIL] Error clicking job card for ID {job_id}")
            raise

    def _extract_job_details(self, job_id: str) -> dict[str, Any] | None:
        try:
            details = JobDetails(
                job_id=job_id,
                job_url=f"https://www.linkedin.com/jobs/view/{job_id}/",
            )

            # Description
            try:
                desc_elem = self.driver.find_element(
                    By.CLASS_NAME, "jobs-description__content"
                )
                try:
                    show_more_btn = desc_elem.find_element(
                        By.CSS_SELECTOR, "button[aria-label*='more']"
                    )
                    show_more_btn.click()
                    time.sleep(0.5)
                except Exception:
                    pass
                details.description = desc_elem.text.strip()
            except NoSuchElementException:
                logger.warning(
                    f"[JOB_DETAIL] Could not find description for job ID {job_id}"
                )
                details.description = ""

            # Criteria
            try:
                criteria_items = []
                for selector in [
                    ".jobs-unified-top-card__job-insight",
                    ".job-details-jobs-unified-top-card__job-insight",
                    ".jobs-unified-top-card__job-insight-view-model-secondary",
                    "span.ui-label",
                ]:
                    criteria_items.extend(
                        self.driver.find_elements(By.CSS_SELECTOR, selector)
                    )

                for item in criteria_items:
                    text = item.text.strip()
                    if "Seniority level" in text or "level" in text.lower():
                        details.seniority = text.replace("Seniority level", "").strip()
                    elif (
                        "Employment type" in text
                        or "Full-time" in text
                        or "Part-time" in text
                    ):
                        details.employment_type = text.replace(
                            "Employment type", ""
                        ).strip()
                    elif "Job function" in text:
                        details.job_function = text.replace("Job function", "").strip()
                    elif "Industries" in text:
                        details.industries = text.replace("Industries", "").strip()
            except Exception as exc:
                logger.debug(f"[JOB_DETAIL] Criteria parsing issue: {exc}")

            # Posted time
            posted_time = None
            for selector in [
                ".jobs-unified-top-card__posted-date",
                ".job-details-jobs-unified-top-card__primary-description",
                ".jobs-unified-top-card__subtitle",
                "span.tvm__text--low-emphasis",
            ]:
                try:
                    posted_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = posted_elem.text.strip()
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
            details.posted_time = posted_time or "Unknown"

            # Applicants
            applicant_count = None
            for selector in [
                ".jobs-unified-top-card__applicant-count",
                ".jobs-unified-top-card__bullet",
                "span.tvm__text--low-emphasis",
                ".job-details-jobs-unified-top-card__primary-description",
            ]:
                try:
                    applicant_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    applicant_text = applicant_elem.text.strip()
                    if "applicant" in applicant_text.lower():
                        match = re.search(r"(\d+)", applicant_text)
                        if match:
                            applicant_count = int(match.group(1))
                            break
                except NoSuchElementException:
                    continue
            details.applicant_count = applicant_count

            # Remote eligibility
            remote_keywords = ["remote", "work from home", "wfh", "hybrid"]
            description_lower = (details.description or "").lower()
            details.remote_eligible = any(
                keyword in description_lower for keyword in remote_keywords
            )
            try:
                workplace_type = self.driver.find_element(
                    By.CSS_SELECTOR, ".jobs-unified-top-card__workplace-type"
                )
                workplace_text = workplace_type.text.strip().lower()
                if "remote" in workplace_text or "hybrid" in workplace_text:
                    details.remote_eligible = True
            except NoSuchElementException:
                pass

            result = details.to_dict()

            # Normalize missing/None fields to "Unknown" to satisfy callers/tests
            for key in [
                "seniority",
                "employment_type",
                "job_function",
                "industries",
                "posted_time",
            ]:
                if not result.get(key):
                    result[key] = "Unknown"

            return result

        except Exception as e:
            logger.error(
                f"[JOB_DETAIL] Error extracting job details: {e}", exc_info=True
            )
            return None

    def _random_delay(
        self, min_delay: float | None = None, max_delay: float | None = None
    ) -> None:
        min_d = min_delay or self.config.request_delay_min
        max_d = max_delay or self.config.request_delay_max
        delay = random.uniform(min_d, max_d)
        logger.debug(f"[JOB_DETAIL] Waiting {delay:.2f} seconds")
        time.sleep(delay)
