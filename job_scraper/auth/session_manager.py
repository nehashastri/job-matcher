"""Selenium session management utilities for LinkedIn sessions."""

from __future__ import annotations

import importlib
import pickle
from collections.abc import Iterable
from pathlib import Path
from typing import Any

try:
    webdriver = importlib.import_module("selenium.webdriver")
    WebDriverException = importlib.import_module("selenium.common.exceptions").WebDriverException  # type: ignore[attr-defined]
    Options = webdriver.ChromeOptions  # type: ignore[attr-defined]
    Service = importlib.import_module("selenium.webdriver.chrome.service").Service  # type: ignore[attr-defined]
    try:
        ChromeDriverManager = importlib.import_module(
            "webdriver_manager.chrome"
        ).ChromeDriverManager  # type: ignore[attr-defined]
    except ModuleNotFoundError:
        ChromeDriverManager = None
except ModuleNotFoundError:  # pragma: no cover - allows import without selenium installed
    webdriver = None
    WebDriverException = Exception
    Options = Any  # type: ignore[assignment]
    Service = Any  # type: ignore[assignment]
    ChromeDriverManager = None


class SessionManager:
    """Create and manage a Chrome webdriver session, plus cookie persistence."""

    def __init__(
        self,
        headless: bool = True,
        user_agent: str | None = None,
        window_size: str = "1280,900",
        driver_path: str | None = None,
        cookie_path: Path = Path("data/.linkedin_cookies.pkl"),
    ) -> None:
        self.headless = headless
        self.user_agent = user_agent
        self.window_size = window_size
        self.driver_path = driver_path
        self.cookie_path = cookie_path
        self._driver: webdriver.Chrome | None = None

    def start(self) -> webdriver.Chrome:
        """Start (or return existing) Chrome webdriver."""
        if self._driver:
            return self._driver

        if webdriver is None:
            raise RuntimeError(
                "Selenium is not installed. Install dependencies via pixi before running authentication."
            )

        options = self._build_options()

        # Use webdriver-manager if available and no explicit path
        if not self.driver_path and ChromeDriverManager:
            try:
                driver_path = ChromeDriverManager().install()
                service = Service(executable_path=driver_path)
                self._driver = webdriver.Chrome(service=service, options=options)
            except Exception:
                # Fallback to Selenium's built-in driver manager
                self._driver = webdriver.Chrome(options=options)
        elif self.driver_path:
            service = Service(executable_path=self.driver_path)
            self._driver = webdriver.Chrome(service=service, options=options)
        else:
            # Let Selenium's built-in manager handle it
            self._driver = webdriver.Chrome(options=options)

        # Reasonable defaults; callers can override if needed
        self._driver.set_page_load_timeout(30)
        return self._driver

    def get_driver(self) -> webdriver.Chrome:
        """Ensure a webdriver is available."""
        return self.start()

    def _build_options(self) -> Options:
        if webdriver is None:
            raise RuntimeError(
                "Selenium is not installed. Install dependencies via pixi before running authentication."
            )
        options = webdriver.ChromeOptions()
        if self.headless:
            # Headless Chrome with new headless mode for stability
            options.add_argument("--headless=new")
        options.add_argument(f"--window-size={self.window_size}")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if self.user_agent:
            options.add_argument(f"--user-agent={self.user_agent}")
        return options

    # Cookie handling -----------------------------------------------------------------
    def load_cookies(self, cookie_path: Path | None = None) -> bool:
        """Load cookies into the current session. Returns True if loaded."""
        driver = self.get_driver()
        path = cookie_path or self.cookie_path
        if not path.exists():
            return False

        with open(path, "rb") as f:
            cookies: Iterable[dict] = pickle.load(f)

        driver.get("https://www.linkedin.com/")
        for cookie in cookies:
            # Selenium requires domain to match current page; silently skip bad cookies
            try:
                driver.add_cookie(cookie)
            except Exception:
                continue
        return True

    def save_cookies(self, cookie_path: Path | None = None) -> None:
        """Persist cookies from the current session."""
        driver = self.get_driver()
        path = cookie_path or self.cookie_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(driver.get_cookies(), f)

    def quit(self) -> None:
        """Cleanly shut down the webdriver."""
        if self._driver:
            try:
                self._driver.quit()
            finally:
                self._driver = None
