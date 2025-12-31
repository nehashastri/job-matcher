import logging
import random
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, TypeVar

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseScraper(ABC):
    """Base class for all job scrapers"""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"scraper.{source_name}")
        self.no_visa_keywords = [
            r"no visa",
            r"no work visa",
            r"no sponsorship",
            r"cannot sponsor",
            r"will not sponsor",
            r"do not sponsor",
            r"us citizen",
            r"us\s+only",
            r"us permanent resident",
            r"permanent resident",
            r"no h-?1b",
            r"no visa sponsorship",
            r"will not provide visa",
        ]

    @abstractmethod
    def scrape(self) -> list[dict[str, Any]]:
        """Scrape jobs from the source"""
        raise NotImplementedError

    def _retry_on_stale_element(
        self, func: Callable[[], T], max_retries: int = 3, delay: float = 1.0
    ) -> T | None:
        """
        Retry a function call if it raises StaleElementReferenceException.

        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds

        Returns:
            Result of the function call, or None if all retries fail
        """
        for attempt in range(max_retries):
            try:
                return func()
            except StaleElementReferenceException:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Stale element, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached for stale element")
                    return None
            except Exception as e:
                self.logger.error(f"Error in retry function: {e}")
                return None
        return None

    def _safe_find_element(self, driver, by, value, default=None):
        """
        Safely find an element, returning default if not found.

        Args:
            driver: Selenium WebDriver instance
            by: Locator strategy (e.g., By.CSS_SELECTOR)
            value: Locator value
            default: Default value to return if element not found

        Returns:
            WebElement or default value
        """
        try:
            return driver.find_element(by, value)
        except NoSuchElementException:
            return default
        except Exception as e:
            self.logger.debug(f"Error finding element {value}: {e}")
            return default

    def _safe_get_text(self, element, default: str = "") -> str:
        """
        Safely get text from an element.

        Args:
            element: WebElement
            default: Default value if text extraction fails

        Returns:
            Element text or default value
        """
        try:
            if element is None:
                return default
            return element.text.strip()
        except StaleElementReferenceException:
            self.logger.debug("Stale element when getting text")
            return default
        except Exception as e:
            self.logger.debug(f"Error getting text: {e}")
            return default

    def _handle_network_error(self, error: Exception, attempt: int, max_retries: int) -> bool:
        """
        Handle network-related errors with exponential backoff.

        Args:
            error: Exception that was raised
            attempt: Current attempt number (0-indexed)
            max_retries: Maximum number of retry attempts

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_retries - 1:
            self.logger.error(f"Max retries ({max_retries}) reached for network error: {error}")
            return False

        # Calculate exponential backoff (2s, 4s, 8s, ..., max 30s)
        backoff = min(2 ** (attempt + 1), 30)
        self.logger.warning(
            f"Network error on attempt {attempt + 1}/{max_retries}: {error}. "
            f"Retrying in {backoff}s..."
        )
        time.sleep(backoff)
        return True

    def _random_delay(self, min_delay: float = 2.0, max_delay: float = 5.0):
        """
        Add a random delay to avoid rate limiting.

        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        delay = random.uniform(min_delay, max_delay)
        self.logger.debug(f"Waiting {delay:.2f} seconds")
        time.sleep(delay)

    def _log_scrape_result(self, jobs_found: int, success: bool = True, error: str | None = None):
        """Log scraping result"""
        if success:
            self.logger.info(f"Successfully scraped {jobs_found} jobs from {self.source_name}")
        else:
            self.logger.error(f"Error scraping {self.source_name}: {error}")

    def _is_posted_today(self, posted_date: Any) -> bool:
        """Check if job was posted today"""
        try:
            if isinstance(posted_date, datetime):
                return posted_date.date() == date.today()
            if isinstance(posted_date, date):
                return posted_date == date.today()
            if isinstance(posted_date, str):
                for fmt in [
                    "%Y-%m-%d",
                    "%m/%d/%Y",
                    "%d/%m/%Y",
                    "%B %d, %Y",
                    "%b %d, %Y",
                ]:
                    try:
                        parsed = datetime.strptime(posted_date, fmt).date()
                        return parsed == date.today()
                    except ValueError:
                        continue
                lowered = posted_date.lower()
                if "today" in lowered:
                    return True
                if "1 day ago" in lowered or "1d" in lowered:
                    return True
            return False
        except Exception as exc:
            self.logger.debug(f"Error parsing date {posted_date}: {exc}")
            return False

    def _is_posted_last_24_hours(self, posted_date: Any) -> bool:
        """Check if job was posted within last 24 hours"""
        try:
            now = datetime.now()
            if isinstance(posted_date, datetime):
                return (now - posted_date).total_seconds() < 86400
            if isinstance(posted_date, str):
                for fmt in [
                    "%Y-%m-%d",
                    "%m/%d/%Y",
                    "%d/%m/%Y",
                    "%B %d, %Y",
                    "%b %d, %Y",
                ]:
                    try:
                        parsed = datetime.strptime(posted_date, fmt)
                        return (now - parsed).total_seconds() < 86400
                    except ValueError:
                        continue
                lowered = posted_date.lower()
                if "today" in lowered:
                    return True
                if "1 day ago" in lowered or "1d" in lowered:
                    return True
            return False
        except Exception as exc:
            self.logger.debug(f"Error parsing date {posted_date}: {exc}")
            return False

    def _is_us_location(self, location: str) -> bool:
        """Check if location is in the US"""
        if not location:
            return False

        location_lower = location.lower()
        us_states = [
            "al",
            "ak",
            "az",
            "ar",
            "ca",
            "co",
            "ct",
            "de",
            "fl",
            "ga",
            "hi",
            "id",
            "il",
            "in",
            "ia",
            "ks",
            "ky",
            "la",
            "me",
            "md",
            "ma",
            "mi",
            "mn",
            "ms",
            "mo",
            "mt",
            "ne",
            "nv",
            "nh",
            "nj",
            "nm",
            "ny",
            "nc",
            "nd",
            "oh",
            "ok",
            "or",
            "pa",
            "ri",
            "sc",
            "sd",
            "tn",
            "tx",
            "ut",
            "vt",
            "va",
            "wa",
            "wv",
            "wi",
            "wy",
        ]

        for state in us_states:
            if (
                f", {state}" in location_lower
                or f" {state} " in location_lower
                or location_lower.endswith(state)
            ):
                return True

        non_us_countries = [
            "uk",
            "canada",
            "germany",
            "france",
            "india",
            "china",
            "japan",
            "australia",
            "london",
            "berlin",
        ]
        for country in non_us_countries:
            if country in location_lower:
                return False

        if any(
            term in location_lower
            for term in ["united states", "usa", "u.s.", "remote - us", "remote (us)", "nationwide"]
        ):
            return True

        return False

    def _sponsors_visa(self, description: str, title: str = "", company: str = "") -> bool:
        """Check if job description indicates visa sponsorship."""
        if not description:
            return True

        text = (description + " " + title + " " + company).lower()
        for pattern in self.no_visa_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                return False

        return True
