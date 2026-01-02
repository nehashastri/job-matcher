"""LinkedIn authentication flow with cookie reuse and retries."""

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
    """Raised when authentication fails."""


class LinkedInAuth:
    def __init__(
        self,
        session_manager: SessionManager,
        login_url: str = "https://www.linkedin.com/login",
        home_url: str = "https://www.linkedin.com/feed/",
        max_retries: int = 5,
        backoff_start_seconds: int = 2,
        backoff_max_seconds: int = 30,
    ) -> None:
        self.session_manager = session_manager
        self.login_url = login_url
        self.home_url = home_url
        self.max_retries = max_retries
        self.backoff_start_seconds = backoff_start_seconds
        self.backoff_max_seconds = backoff_max_seconds

    def login(self, email: str, password: str) -> bool:
        """Attempt login, reusing cookies first; falls back to credential login."""
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
            submit_el = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@type='submit' or @aria-label='Sign in']")
                )
            )
        except TimeoutException as exc:
            raise LinkedInAuthError("Login form not available") from exc

        email_el.clear()
        email_el.send_keys(email)
        password_el.clear()
        password_el.send_keys(password)
        submit_el.click()

        # Wait for either feed page or an error indicator
        try:
            WebDriverWait(driver, 15).until(EC.url_contains("/feed"))
        except TimeoutException as exc:
            # Check for error message on login page (invalid credentials)
            if self._has_invalid_credentials_error(driver):
                raise LinkedInAuthError("Invalid LinkedIn credentials") from exc
            raise

    def _is_logged_in(self) -> bool:
        driver = self.session_manager.get_driver()
        driver.get(self.home_url)
        return "/feed" in driver.current_url and "login" not in driver.current_url

    def _has_invalid_credentials_error(self, driver: Any) -> bool:
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
        delay = min(
            self.backoff_start_seconds * (2 ** (attempt - 1)), self.backoff_max_seconds
        )
        time.sleep(delay)
