"""Selenium session management utilities for LinkedIn sessions."""

from __future__ import annotations

import importlib
import pickle
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    webdriver = importlib.import_module("selenium.webdriver")
    WebDriverException = getattr(
        importlib.import_module("selenium.common.exceptions"),
        "WebDriverException",
        Exception,
    )
    ChromeService = getattr(
        importlib.import_module("selenium.webdriver.chrome.service"),
        "Service",
        None,
    )
    ChromeDriverManager = None
    try:
        ChromeDriverManager = getattr(
            importlib.import_module("webdriver_manager.chrome"),
            "ChromeDriverManager",
            None,
        )
    except ModuleNotFoundError:
        ChromeDriverManager = None
except (
    ModuleNotFoundError
):  # pragma: no cover - allows import without selenium installed
    webdriver = None
    WebDriverException = Exception
    ChromeService = None
    ChromeDriverManager = None

if TYPE_CHECKING:
    from typing import Any as ChromeWebDriver
else:  # pragma: no cover - typing only
    ChromeWebDriver = Any


class SessionManager:
    """Create and manage a Chrome webdriver session, plus cookie persistence."""

    def __init__(
        self,
        headless: bool = True,
        user_agent: str | None = None,
        window_size: str = "1280,900",
        driver_path: str | None = None,
        cookie_path: Path = Path(__file__).parent.parent / "data/.linkedin_cookies.pkl",
    ) -> None:
        self.headless = headless
        self.user_agent = user_agent
        self.window_size = window_size
        self.driver_path = driver_path
        self.cookie_path = cookie_path
        self._driver: ChromeWebDriver | None = None

    def start(self) -> ChromeWebDriver:
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
                if ChromeService:
                    service = ChromeService(executable_path=driver_path)
                    self._driver = webdriver.Chrome(service=service, options=options)
                else:
                    self._driver = webdriver.Chrome(options=options)
            except Exception:
                # Fallback to Selenium's built-in driver manager
                self._driver = webdriver.Chrome(options=options)
        elif self.driver_path:
            if ChromeService:
                service = ChromeService(executable_path=self.driver_path)
                self._driver = webdriver.Chrome(service=service, options=options)
            else:
                self._driver = webdriver.Chrome(options=options)
        else:
            # Let Selenium's built-in manager handle it
            self._driver = webdriver.Chrome(options=options)

        # Reasonable defaults; callers can override if needed
        if self._driver is None:  # Defensive guard for type-checkers
            raise RuntimeError("Failed to initialize Chrome webdriver.")
        self._driver.set_page_load_timeout(30)
        return self._driver

    def get_driver(self) -> ChromeWebDriver:
        """Ensure a webdriver is available."""
        return self.start()

    def _build_options(self) -> Any:
        if webdriver is None:
            raise RuntimeError(
                "Selenium is not installed. Install dependencies via pixi before running authentication."
            )
        chrome_options_cls = getattr(webdriver, "ChromeOptions", None)
        if chrome_options_cls is None:
            raise RuntimeError("ChromeOptions not available in selenium.webdriver")
        options = chrome_options_cls()

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
