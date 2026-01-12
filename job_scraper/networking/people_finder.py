from __future__ import annotations

import logging
import time
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


class PeopleFinder:
    def __init__(self, driver=None, wait=None, logger=None):
        self.driver = driver
        self.wait = wait
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def safe_text(card, selector: str) -> str:
        logging.getLogger(__name__).info(f"[ENTER] {__file__}::PeopleFinder.safe_text")
        """
        Extracts text from a card using a CSS selector, tries multiple selectors if comma-separated.
        Args:
            card: Selenium WebElement for the card
            selector (str): CSS selector(s), comma-separated
        Returns:
            str: Extracted text or empty string
        """
        selectors = [part.strip() for part in selector.split(",")]
        for sel in selectors:
            try:
                elem = card.find_element(By.CSS_SELECTOR, sel)
                return elem.text.strip()
            except Exception:
                continue
        return ""

    def scrape_people_cards(self, role: str, company: str) -> list[dict[str, str]]:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.iterate_pages")
        if self.driver is None:
            raise RuntimeError("Selenium driver is not initialized.")
        query = f"{role} at {company}".strip()
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
        self.logger.info(f"[PEOPLE_SEARCH] '{query}' (new tab)")
        self.logger.info(f"[PEOPLE_SEARCH] Visiting URL: {search_url}")
        self.driver.execute_script(f"window.open('{search_url}', '_blank');")
        new_handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(new_handle)
        self.logger.info(
            f"[PEOPLE_SEARCH] Switched to new tab, URL: {self.driver.current_url}"
        )
        self._click_people_filter()
        self._ensure_people_url(search_url)
        self.logger.info(
            f"[PEOPLE_SEARCH] After ensure_people_url, current URL: {self.driver.current_url}"
        )
        self._wait_for_results()
        page_count = 0
        all_profiles = []
        while True:
            self.logger.info(
                f"[PEOPLE_SEARCH] Visiting people page {page_count + 1}: {self.driver.current_url}"
            )
            self.logger.info(
                f"[PEOPLE_SEARCH] On page {page_count + 1}, URL: {self.driver.current_url}"
            )
            self._scroll_results()
            page_profiles = self._scrape_current_page(role, company)
            for p in page_profiles:
                self.logger.info(
                    f"[PEOPLE_SEARCH] Profile: name='{p.get('name')}', title='{p.get('title')}', current_position='{p.get('current_position')}'"
                )
            all_profiles.extend(page_profiles)
            page_count += 1
            if page_count >= 3:  # Example: stop after 3 pages
                break
            if not self._click_next_page():
                break
            self.logger.info(
                f"[PEOPLE_SEARCH] After pagination, current URL: {self.driver.current_url}"
            )
            time.sleep(1)
        return all_profiles

    def _safe_get(self, url: str, retries: int = 2, delay: float = 2.0) -> bool:
        if self.driver is None:
            raise RuntimeError("Selenium driver is not initialized.")
        self.driver.get(url)
        time.sleep(delay)
        return True

    def _llm_batch_profile_match(
        self, profiles: list[dict[str, str]], query: str
    ) -> list[dict[str, str]]:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._llm_batch_profile_match"
        )
        """
        Use LLM to decide which LinkedIn profile cards match the search query, using only the title field.
        Returns a list of matched profiles with all required columns.
        """
        try:
            with open("data/LLM_people_match.txt", "r", encoding="utf-8") as f:
                _ = f.read().strip()  # prompt is not used
        except Exception:
            pass  # prompt is not used
        # This is a stub; real implementation should return a list
        return []

    def _click_people_filter(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._click_people_filter"
        )
        if self.driver is None:
            raise RuntimeError("Selenium driver is not initialized.")
        """Ensure the People filter/tab is selected."""
        try:
            filter_selectors = [
                "button[aria-label='People']",
                "button[aria-label='People filter.']",
                "a[href*='search/results/people']",
                "button[data-test-search-vertical-filter='PEOPLE']",
                "a[data-test-search-vertical-filter='PEOPLE']",
            ]
            find_element = getattr(self.driver, "find_element", None)
            if find_element:
                for selector in filter_selectors:
                    try:
                        element = find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        time.sleep(0.5)
                        return
                    except Exception:
                        continue
            self.logger.debug(
                "[PEOPLE_SEARCH] People filter not found; continuing anyway"
            )
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Could not click People filter: {exc}")

    def _click_next_page(self) -> bool:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._click_next_page"
        )
        if self.driver is None:
            raise RuntimeError("Selenium driver is not initialized.")
        """
        Clicks the 'Next' button on LinkedIn people search results, if present.
        Returns True if next page was clicked, False otherwise.
        """
        try:
            next_btn_selectors = [
                "button[aria-label='Next']",
                "button[aria-label='Next page']",
                "button[aria-label='Next Page']",
                "li.artdeco-pagination__indicator--number button",
                "button[data-testid='pagination-controls-next-button-visible']",
            ]
            find_element = getattr(self.driver, "find_element", None)
            if find_element:
                for selector in next_btn_selectors:
                    try:
                        btn = find_element(By.CSS_SELECTOR, selector)
                        if btn.is_enabled():
                            btn.click()
                            time.sleep(1)
                            return True
                    except Exception:
                        continue
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Could not click next page: {exc}")
        return False

    # Removed unused legacy function _search_via_bar

    def _scrape_current_page(self, role: str, company: str) -> list[dict[str, str]]:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._scrape_current_page"
        )
        """
        Scrape all profile cards on the current page, returning a list of profile dicts
        with direct references to card, connect button, and message button.
        """
        if self.driver is None:
            raise RuntimeError("Selenium driver is not initialized.")
        profiles = []
        try:
            wait_until = getattr(self.wait, "until", None)
            if wait_until:
                wait_until(
                    EC.presence_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            "[data-view-name='people-search-result'], li.reusable-search__result-container, div.reusable-search__result-container, div.entity-result, div.search-result__occluded-item",
                        )
                    )
                )
        except Exception:
            self.logger.info("[PEOPLE_SEARCH] No results container found on page")
            self.logger.info(
                f"[PEOPLE_SEARCH] No profile cards found for this search (URL: {getattr(self.driver, 'current_url', '')})"
            )
            self._dump_page(f"people_page_{int(time.time())}.html")
            return profiles
        find_elements = getattr(self.driver, "find_elements", None)
        find_element = getattr(self.driver, "find_element", None)
        cards = []
        if find_elements:
            cards = find_elements(
                By.CSS_SELECTOR,
                "[data-view-name='people-search-result'], li.reusable-search__result-container, div.reusable-search__result-container, div.search-result__occluded_item",
            )
            if not cards:
                cards = find_elements(
                    By.CSS_SELECTOR,
                    "div.entity-result, div.search-result__info, div.entity-result__content",
                )
        if not cards:
            try:
                body_text = ""
                if find_element:
                    body_elem = find_element(By.TAG_NAME, "body")
                    body_text = body_elem.text
                if "No results found" in body_text:
                    self.logger.info("[PEOPLE_SEARCH] No results found message on page")
                else:
                    snippet = body_text[:400].replace("\n", " ")
                    self.logger.info(
                        f"[PEOPLE_SEARCH] No profile cards found on this page; body snippet='{snippet}'"
                    )
                self.logger.info(
                    f"[PEOPLE_SEARCH] No profile cards found for this search (URL: {getattr(self.driver, 'current_url', '')})"
                )
                self._dump_page(f"people_page_{int(time.time())}.html")
            except Exception:
                self.logger.info("[PEOPLE_SEARCH] No profile cards found on this page")
                self.logger.info(
                    f"[PEOPLE_SEARCH] No profile cards found for this search (URL: {getattr(self.driver, 'current_url', '')})"
                )
                self._dump_page(f"people_page_{int(time.time())}.html")
        else:
            self.logger.info(f"[PEOPLE_SEARCH] Found {len(cards)} cards on page")
        for card in cards:
            profile = self._extract_profile(card, role, company)
            if profile and (
                profile["profile_url"] or profile["name"] or profile["title"]
            ):
                profiles.append(profile)
        if not profiles:
            self.logger.info(
                f"[PEOPLE_SEARCH] No profile cards found for this search (URL: {getattr(self.driver, 'current_url', '')})"
            )
        return profiles

    def _wait_for_results(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._wait_for_results"
        )
        if self.wait is None:
            raise RuntimeError("Selenium WebDriverWait is not initialized.")
        try:
            wait_until = getattr(self.wait, "until", None)
            if wait_until:
                wait_until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.entity-result__item")
                    )
                )
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Wait for results failed: {exc}")

    def _scroll_results(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._scroll_results"
        )
        try:
            execute_script = getattr(self.driver, "execute_script", None)
            if execute_script:
                execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Scroll failed: {exc}")

    def _ensure_people_url(self, url: str) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._ensure_people_url"
        )
        try:
            current_url = getattr(self.driver, "current_url", "")
            if "search/results/people" not in (current_url or ""):
                get_func = getattr(self.driver, "get", None)
                if get_func:
                    get_func(url)
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Ensure people URL failed: {exc}")

    def _dump_page(self, filename: str) -> None:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._dump_page")
        try:
            html = getattr(self.driver, "page_source", "")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Dump page failed: {exc}")

    def _count_selectors(self, selectors: list[str], label: str = ""):
        if self.driver is None:
            raise RuntimeError("Selenium driver is not initialized.")
        try:
            find_elements = getattr(self.driver, "find_elements", None)
            count = 0
            if find_elements and selectors:
                count = len(find_elements(By.CSS_SELECTOR, selectors[0]))
            self.logger.info(f"[PEOPLE_SEARCH] Selector '{label}' count={count}")
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Failed counting selectors: {exc}")

    def _log_debug_counts(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._log_debug_counts"
        )
        try:
            selectors = {
                "[data-view-name='people-search-result']": "[data-view-name='people-search-result']",
                "li.reusable-search__result-container": "li.reusable-search__result-container",
                "div.reusable-search__result-container": "div.reusable-search__result-container",
                "div.search-result__occluded-item": "div.search-result__occluded-item",
                "div.entity-result": "div.entity-result",
                "div.search-result__info": "div.search-result__info",
                "div.entity-result__content": "div.entity-result__content",
            }
            find_elements = getattr(self.driver, "find_elements", None)
            if find_elements:
                for label, selector in selectors.items():
                    count = len(find_elements(By.CSS_SELECTOR, selector))
                    self.logger.info(
                        f"[PEOPLE_SEARCH] Selector '{label}' count={count}"
                    )
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Failed counting selectors: {exc}")

    def _extract_profile(self, card, role: str, company: str) -> dict[str, str] | None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._extract_profile"
        )
        """
        Extracts minimal profile info from a LinkedIn people search card.
        Returns a dict with name, profile_url, company, message_button_available.
        """
        name = ""
        message_button_available = False
        profile_url = ""
        # Extract profile_url as before
        try:
            link_elem = None
            a_tags = card.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
            for a in a_tags:
                href = a.get_attribute("href")
                if href and href.startswith("https://www.linkedin.com/in/"):
                    link_elem = a
                    break
            if not link_elem and a_tags:
                link_elem = a_tags[0]
            if link_elem:
                profile_url = link_elem.get_attribute("href") or ""
        except Exception:
            pass

        try:
            card_text = card.get_attribute("innerHTML")
            self.logger.info(f"[PEOPLE_SEARCH][DEBUG] Raw card_text: {card_text}")
            import re

            # Remove all HTML tags, replace with a space to preserve word boundaries
            text = re.sub(r"<[^>]+>", " ", card_text)
            # Collapse multiple spaces/newlines to a single space
            text = re.sub(r"[ \t\r\f\v]+", ";", text)
            text = re.sub(r"\n+", "; ", text)
            name = text.strip()
            self.logger.info(f"[PEOPLE_SEARCH][DEBUG] Cleaned text: {name}")
            # Message button: check if 'message' is in the cleaned text (case-insensitive)
            message_button_available = "message" in name.lower()
        except Exception:
            name = ""
            message_button_available = False

        # Log extracted features after all fields are set
        self.logger.info(
            f"[PEOPLE_SEARCH][EXTRACT] name='{name}', message_button_available={'TRUE' if message_button_available else 'FALSE'}"
        )

        return {
            "name": name,
            "profile_url": profile_url,
            "company": company,
            "message_button_available": "TRUE" if message_button_available else "FALSE",
        }
