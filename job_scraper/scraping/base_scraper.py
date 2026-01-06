import logging
import random
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
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
                    self.logger.warning(
                        f"Stale element, retrying ({attempt + 1}/{max_retries})..."
                    )
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

    def _handle_network_error(
        self, error: Exception, attempt: int, max_retries: int
    ) -> bool:
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
            self.logger.error(
                f"Max retries ({max_retries}) reached for network error: {error}"
            )
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

    def _log_scrape_result(
        self, jobs_found: int, success: bool = True, error: str | None = None
    ):
        """Log scraping result"""
        if success:
            self.logger.info(
                f"Successfully scraped {jobs_found} jobs from {self.source_name}"
            )
        else:
            self.logger.error(f"Error scraping {self.source_name}: {error}")

    def _sponsors_visa(
        self, description: str, title: str = "", company: str = ""
    ) -> bool:
        """Check if job description indicates visa sponsorship."""
        if not description:
            return True

        text = (description + " " + title + " " + company).lower()
        for pattern in self.no_visa_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                return False

        return True
