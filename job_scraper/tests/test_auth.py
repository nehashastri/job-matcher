"""Unit tests for LinkedIn authentication and session management (Phase 1)."""

from __future__ import annotations

import importlib
import pickle
from pathlib import Path

import pytest

try:
    _selenium_exceptions = importlib.import_module("selenium.common.exceptions")
    TimeoutException = _selenium_exceptions.TimeoutException  # type: ignore[attr-defined]
    WebDriverException = _selenium_exceptions.WebDriverException  # type: ignore[attr-defined]
except (
    ModuleNotFoundError
):  # pragma: no cover - fallback for type checking when selenium not installed
    TimeoutException = Exception
    WebDriverException = Exception

from auth.linkedin_auth import LinkedInAuth, LinkedInAuthError
from auth.session_manager import SessionManager


class FakeDriver:
    def __init__(self):
        self.current_url = "https://www.linkedin.com/login"
        self.added_cookies: list[dict] = []
        self.cookies_to_return: list[dict] = []
        self.visited: list[str] = []

    # Selenium-like methods
    def get(self, url: str):
        self.visited.append(url)
        self.current_url = url

    def add_cookie(self, cookie: dict):
        self.added_cookies.append(cookie)

    def get_cookies(self):
        return self.cookies_to_return

    def set_page_load_timeout(self, *_):
        return None

    # Element lookup stubs for login
    def find_element(self, *_args, **_kwargs):
        raise TimeoutException("No element")

    def quit(self):
        return None


@pytest.fixture
def fake_session(tmp_path) -> SessionManager:
    # Build a session manager that uses our FakeDriver
    mgr = SessionManager()
    mgr._driver = FakeDriver()  # type: ignore[attr-defined]
    # Override cookie path to temp dir
    mgr.cookie_path = tmp_path / ".linkedin_cookies.pkl"
    return mgr


def test_load_cookies_from_file(fake_session: SessionManager, tmp_path):
    cookie_file = tmp_path / ".linkedin_cookies.pkl"
    cookies = [{"name": "li_at", "value": "abc", "domain": "linkedin.com"}]
    with open(cookie_file, "wb") as f:
        pickle.dump(cookies, f)

    loaded = fake_session.load_cookies(cookie_file)

    assert loaded is True
    driver = fake_session.get_driver()
    assert driver.added_cookies[0]["name"] == "li_at"


def test_load_cookies_missing_file(fake_session: SessionManager):
    assert fake_session.load_cookies(Path("/nonexistent.pkl")) is False


def test_login_success_with_retry(monkeypatch, fake_session: SessionManager):
    auth = LinkedInAuth(fake_session, max_retries=3, backoff_start_seconds=0, backoff_max_seconds=0)

    calls = {"count": 0}

    def succeed_on_third(driver, email, password):
        calls["count"] += 1
        if calls["count"] < 3:
            raise WebDriverException("temporary")
        driver.current_url = "https://www.linkedin.com/feed/"

    monkeypatch.setattr(auth, "_login_once", succeed_on_third)
    monkeypatch.setattr(
        auth, "_is_logged_in", lambda: fake_session.get_driver().current_url.endswith("/feed/")
    )

    assert auth.login("user", "pass") is True
    assert calls["count"] == 3


def test_login_invalid_credentials(monkeypatch, fake_session: SessionManager):
    auth = LinkedInAuth(fake_session, max_retries=2, backoff_start_seconds=0, backoff_max_seconds=0)

    def invalid(driver, email, password):
        raise LinkedInAuthError("Invalid LinkedIn credentials")

    monkeypatch.setattr(auth, "_login_once", invalid)

    with pytest.raises(LinkedInAuthError):
        auth.login("user", "bad")


def test_login_uses_cookies_first(monkeypatch, fake_session: SessionManager, tmp_path):
    # Prepare cookie file and mark driver as already logged in once cookies load
    cookie_file = tmp_path / ".linkedin_cookies.pkl"
    cookies = [{"name": "li_at", "value": "abc", "domain": "linkedin.com"}]
    with open(cookie_file, "wb") as f:
        pickle.dump(cookies, f)

    fake_session.cookie_path = cookie_file
    driver = fake_session.get_driver()
    driver.current_url = "https://www.linkedin.com/feed/"

    auth = LinkedInAuth(fake_session)

    # Ensure we do not call _login_once when cookies already log us in
    monkeypatch.setattr(
        auth,
        "_login_once",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("should not be called")),
    )

    assert auth.login("user", "pass") is True


def test_login_fails_after_max_retries(monkeypatch, fake_session: SessionManager):
    auth = LinkedInAuth(fake_session, max_retries=2, backoff_start_seconds=0, backoff_max_seconds=0)

    def always_timeout(driver, email, password):
        raise TimeoutException("timeout")

    monkeypatch.setattr(auth, "_login_once", always_timeout)

    with pytest.raises(LinkedInAuthError):
        auth.login("user", "pass")
