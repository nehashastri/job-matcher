"""
linkedin_auth.py

Handles LinkedIn authentication using Selenium, with cookie reuse and retry logic.

Features:
- Robust login with retries and exponential backoff
- Integrates with SessionManager for session persistence
- Raises LinkedInAuthError on authentication failure

Variables:
    NoSuchElementException, TimeoutException, WebDriverException: Selenium exceptions for error handling
    By, EC, WebDriverWait: Selenium utilities for element selection and waiting

Classes:
    LinkedInAuthError: Custom exception for authentication failures
    LinkedInAuth: Main class for handling LinkedIn login and session management
        session_manager: Manages Selenium sessions and cookies
        login_url: LinkedIn login page URL
        home_url: LinkedIn home/feed page URL
        max_retries: Maximum number of login attempts
        backoff_start_seconds: Initial backoff time for retries
        backoff_max_seconds: Maximum backoff time for retries

Functions:
    __init__: Initializes LinkedInAuth with session manager and login parameters
    login: Attempts login, reusing cookies first, falls back to credential login
    _login_once: Performs a single login attempt
    _is_logged_in: Checks if user is logged in
    _has_invalid_credentials_error: Checks for invalid credentials error
    _backoff: Implements exponential backoff for retries
"""

from __future__ import annotations

import importlib
import time
from typing import Any

try:
    _selenium_exc = importlib.import_module("selenium.common.exceptions")
    NoSuchElementException = getattr(_selenium_exc, "NoSuchElementException", Exception)
    TimeoutException = getattr(_selenium_exc, "TimeoutException", Exception)
    WebDriverException = getattr(_selenium_exc, "WebDriverException", Exception)
    By = getattr(importlib.import_module("selenium.webdriver.common.by"), "By", None)
    EC = importlib.import_module("selenium.webdriver.support.expected_conditions")
    WebDriverWait = getattr(
        importlib.import_module("selenium.webdriver.support.ui"), "WebDriverWait", None
    )
except (
    ModuleNotFoundError
):  # pragma: no cover - allows import without selenium installed
    NoSuchElementException = TimeoutException = WebDriverException = Exception
    By = EC = WebDriverWait = None

from auth.session_manager import SessionManager


class LinkedInAuthError(Exception):
    """
    Raised when authentication fails.
    Used to signal login errors or invalid credentials.
    """


class LinkedInAuth:
    """
    Main class for handling LinkedIn login and session management.
    Attributes:
        session_manager (SessionManager): Manages Selenium sessions and cookies
        login_url (str): LinkedIn login page URL
        home_url (str): LinkedIn home/feed page URL
        max_retries (int): Maximum number of login attempts
        backoff_start_seconds (int): Initial backoff time for retries
        backoff_max_seconds (int): Maximum backoff time for retries
    """

    def __init__(
        self,
        session_manager: SessionManager,
        login_url: str = "https://www.linkedin.com/login",
        home_url: str = "https://www.linkedin.com/feed/",
        max_retries: int = 5,
        backoff_start_seconds: int = 2,
        backoff_max_seconds: int = 30,
    ) -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        # SessionManager instance for managing Selenium driver and cookies
        self.session_manager = session_manager
        # LinkedIn login page URL
        self.login_url = login_url
        # LinkedIn home/feed page URL
        self.home_url = home_url
        # Maximum number of login attempts before giving up
        self.max_retries = max_retries
        # Initial backoff time (seconds) for retrying login
        self.backoff_start_seconds = backoff_start_seconds
        # Maximum backoff time (seconds) for retrying login
        self.backoff_max_seconds = backoff_max_seconds

    def login(self, email: str, password: str) -> bool:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.login")
        """
        Attempt login, reusing cookies first; falls back to credential login.
        Args:
            email (str): LinkedIn account email
            password (str): LinkedIn account password
        Returns:
            bool: True if login successful, False otherwise
        Raises:
            LinkedInAuthError: If login fails after retries or invalid credentials
        """
        if (WebDriverWait is None or By is None) and getattr(
            self.session_manager, "_driver", None
        ) is None:
            raise LinkedInAuthError(
                "Selenium is not installed. Install dependencies via pixi before running authentication."
            )
        driver = self.session_manager.get_driver()

        # Try existing cookies first
        if self.session_manager.load_cookies():
            if self._is_logged_in():
                return True

        # Fresh login with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                self._login_once(driver, email, password)
                if not self._is_logged_in():
                    raise LinkedInAuthError("Login did not reach feed page")
                self.session_manager.save_cookies()
                return True
            except LinkedInAuthError:
                # Invalid credentials or explicit auth failure: do not retry
                raise
            except (TimeoutException, WebDriverException):
                if attempt >= self.max_retries:
                    raise LinkedInAuthError("Login failed after retries")
                self._backoff(attempt)

        raise LinkedInAuthError("Login failed")

    def _login_once(self, driver: Any, email: str, password: str) -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._login_once")
        """
        Perform a single login attempt using credentials.
        Args:
            driver (Any): Selenium WebDriver instance
            email (str): LinkedIn account email
            password (str): LinkedIn account password
        Raises:
            LinkedInAuthError: If login form is not available or credentials are invalid
        """
        driver.get(self.login_url)

        if WebDriverWait is None or By is None or EC is None:
            raise LinkedInAuthError(
                "Selenium is not installed. Install dependencies via pixi before running authentication."
            )

        wait = WebDriverWait(driver, 15)
        try:
            email_el = wait.until(EC.presence_of_element_located((By.ID, "username")))
            password_el = wait.until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@type='submit' or @aria-label='Sign in']")
                )
            )
        except TimeoutException as exc:
            raise LinkedInAuthError("Login form not available") from exc

        # Fill in login form and submit
        email_el.clear()
        email_el.send_keys(email)
        password_el.clear()
        password_el.send_keys(password)

        # Wait for either feed page or an error indicator
        try:
            WebDriverWait(driver, 15).until(EC.url_contains("/feed"))
        except TimeoutException as exc:
            # Check for error message on login page (invalid credentials)
            if self._has_invalid_credentials_error(driver):
                raise LinkedInAuthError("Invalid LinkedIn credentials") from exc
            raise

    def _is_logged_in(self) -> bool:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._is_logged_in")
        """
        Check if user is logged in by verifying current URL.
        Returns:
            bool: True if logged in, False otherwise
        """
        driver = self.session_manager.get_driver()
        driver.get(self.home_url)
        return "/feed" in driver.current_url and "login" not in driver.current_url

    def _has_invalid_credentials_error(self, driver: Any) -> bool:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._has_invalid_credentials_error"
        )
        """
        Check for invalid credentials error on login page.
        Args:
            driver (Any): Selenium WebDriver instance
        Returns:
            bool: True if error is displayed, False otherwise
        """
        if By is None:
            return False
        try:
            error_el = driver.find_element(
                By.CSS_SELECTOR, ".alert.error, .form__message--error"
            )
            return error_el.is_displayed()
        except NoSuchElementException:
            return False

    def _backoff(self, attempt: int) -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._backoff")
        """
        Implements exponential backoff for login retries.
        Args:
            attempt (int): Current attempt number
        """
        delay = min(
            self.backoff_start_seconds * (2 ** (attempt - 1)), self.backoff_max_seconds
        )
        time.sleep(delay)
