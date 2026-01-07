"""LinkedIn People search helper for Phase 6 networking."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Generator
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class PeopleFinder:
    """Search LinkedIn People results for a given role at a company."""

    def __init__(
        self, driver, wait: WebDriverWait, logger: logging.Logger | None = None
    ):
        self.driver = driver
        self.wait = wait
        self.logger = logger or logging.getLogger(__name__)
        self.base_url = "https://www.linkedin.com"

    def search(
        self, role: str, company: str, pages: int | None = None
    ) -> list[dict[str, Any]]:
        """Search LinkedIn People for `role at company` and return profile dictionaries.

        This aggregates results across pages (bounded by `pages` when provided).
        Use `iterate_pages` when you need to act on each page before paginating.
        """
        profiles: list[dict[str, Any]] = []
        try:
            for page_index, page_profiles in enumerate(
                self.iterate_pages(role, company, pages=pages)
            ):
                profiles.extend(page_profiles)
                self.logger.info(
                    f"[PEOPLE_SEARCH] Page {page_index + 1}: {len(page_profiles)} profiles scraped"
                )
        except Exception as exc:
            self.logger.error(f"[PEOPLE_SEARCH] Error during search: {exc}")
        return profiles

    def iterate_pages(
        self, role: str, company: str, pages: int | None = None
    ) -> Generator[list[dict[str, Any]], None, None]:
        """Yield profiles page-by-page while staying on the current tab.

        This lets callers perform per-page actions before advancing to the next page.
        """
        query = f"{role} at {company}".strip()
        search_url = (
            f"{self.base_url}/search/results/people/?keywords={quote_plus(query)}"
        )
        self.logger.info(f"[PEOPLE_SEARCH] '{query}'")

        if not self._search_via_bar(query):
            if not self._safe_get(search_url):
                self.logger.error("[PEOPLE_SEARCH] Unable to load search URL")
                return

        self._click_people_filter()
        self._ensure_people_url(search_url)
        self._wait_for_results()
        try:
            self.logger.info(f"[PEOPLE_SEARCH] Current URL: {self.driver.current_url}")
        except Exception:
            pass

        page_count = 0
        while True:
            self._scroll_results()
            page_profiles = self._scrape_current_page(role, company)
            for p in page_profiles:
                self.logger.info(
                    f"[PEOPLE_SEARCH] Profile: name='{p.get('name')}', title='{p.get('title')}', match={p.get('is_role_match')}"
                )
            yield page_profiles

            page_count += 1
            if pages is not None and page_count >= pages:
                break
            if not self._click_next_page():
                break
            time.sleep(1)

    def _click_people_filter(self) -> None:
        """Ensure the People filter/tab is selected."""
        try:
            filter_selectors = [
                "button[aria-label='People']",
                "button[aria-label='People filter.']",
                "a[href*='search/results/people']",
                "button[data-test-search-vertical-filter='PEOPLE']",
                "a[data-test-search-vertical-filter='PEOPLE']",
            ]
            for selector in filter_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
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

    def _search_via_bar(self, query: str) -> bool:
        """Try to mimic user typing into LinkedIn top search bar."""
        try:
            if not self._safe_get(self.base_url):
                return False
            search_box = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[aria-label='Search']")
                )
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.ENTER)
            time.sleep(2)
            self.logger.info("[PEOPLE_SEARCH] Submitted query via top search bar")
            return True
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Search bar path failed: {exc}")
            return False

    def _scrape_current_page(self, role: str, company: str) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "[data-view-name='people-search-result'], li.reusable-search__result-container, div.reusable-search__result-container, div.entity-result, div.search-result__occluded-item",
                    )
                )
            )
        except Exception:
            self.logger.info("[PEOPLE_SEARCH] No results container found on page")
            self._dump_page(f"people_page_{int(time.time())}.html")
            return profiles

        cards = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[data-view-name='people-search-result'], li.reusable-search__result-container, div.reusable-search__result-container, div.search-result__occluded-item",
        )
        if not cards:
            cards = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.entity-result, div.search-result__info, div.entity-result__content",
            )

        if not cards:
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                if "No results found" in body_text:
                    self.logger.info("[PEOPLE_SEARCH] No results found message on page")
                else:
                    snippet = body_text[:400].replace("\n", " ")
                    self.logger.info(
                        f"[PEOPLE_SEARCH] No profile cards found on this page; body snippet='{snippet}'"
                    )
                    self._dump_page(f"people_page_{int(time.time())}.html")
            except Exception:
                self.logger.info("[PEOPLE_SEARCH] No profile cards found on this page")
                self._dump_page(f"people_page_{int(time.time())}.html")
        else:
            self.logger.info(f"[PEOPLE_SEARCH] Found {len(cards)} cards on page")

        for card in cards:
            profile = self._extract_profile(card, role, company)
            if profile:
                profiles.append(profile)
        return profiles

    def _scroll_results(self) -> None:
        try:
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(1)
        except Exception:
            pass

    def _wait_for_results(self) -> None:
        try:
            # Wait up to 30s for results to load
            self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "[data-view-name='people-search-result'], li.reusable-search__result-container, div.reusable-search__result-container, div.entity-result, div.search-result__occluded-item",
                    )
                )
            )
            self.logger.info("[PEOPLE_SEARCH] Results loaded successfully")
        except Exception as exc:
            self.logger.warning(
                f"[PEOPLE_SEARCH] Results wait timeout/error (will try to parse anyway): {exc}"
            )
            # Log selector counts for debugging
            self._log_debug_counts()

    def _dump_page(self, filename: str) -> None:
        try:
            logs_dir = Path(__file__).resolve().parent.parent / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            path = logs_dir / filename
            html = self.driver.page_source
            path.write_text(html, encoding="utf-8")
            self.logger.info(f"[PEOPLE_SEARCH] Saved page dump to {path}")
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Failed to dump page: {exc}")

    def _ensure_people_url(self, search_url: str) -> None:
        try:
            if "search/results/people" not in (self.driver.current_url or ""):
                self._safe_get(search_url)
        except Exception:
            self._safe_get(search_url)

    def _log_debug_counts(self) -> None:
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
            for label, selector in selectors.items():
                count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
                self.logger.info(f"[PEOPLE_SEARCH] Selector '{label}' count={count}")
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Failed counting selectors: {exc}")

    def _extract_profile(self, card, role: str, company: str) -> dict[str, Any] | None:
        try:
            link_elem = self._safe_find(
                card,
                By.CSS_SELECTOR,
                "a[data-view-name='search-result-lockup-title'], a.app-aware-link",
            )
            profile_url = link_elem.get_attribute("href") if link_elem else ""
            name = self._safe_text(
                card,
                "a[data-view-name='search-result-lockup-title'], span.entity-result__title-text span[aria-hidden='true']",
            )
            if not name:
                name = self._safe_text(card, "span[dir='ltr']")
            title = self._safe_text(
                card,
                "p[data-view-name='search-result-subtitle'], div.entity-result__primary-subtitle, div.entity-result__secondary-subtitle, p._57a34c9c._3f883ddb._0da3dbae._1ae18243",
            )
            if title and "mutual connection" in title.lower():
                title = ""

            connection_status = self._extract_connection_status(card)
            is_match = self._is_role_company_match(title, role, company)
            if profile_url or name or title:
                return {
                    "name": name,
                    "title": title,
                    "profile_url": profile_url,
                    "connection_status": connection_status,
                    "is_role_match": is_match,
                }
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Failed to parse profile card: {exc}")
        return None

    def _click_next_page(self) -> bool:
        try:
            next_selectors = [
                "button[aria-label='Next']",
                "button.artdeco-pagination__button--next",
            ]
            for selector in next_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.get_attribute("disabled"):
                        return False
                    btn.click()
                    return True
                except Exception:
                    continue
            self.logger.debug(
                "[PEOPLE_SEARCH] No next button found; stopping pagination"
            )
            return False
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Could not paginate: {exc}")
            return False

    @staticmethod
    def _safe_find(card, by, value):
        selectors = [part.strip() for part in value.split(",")]
        for selector in selectors:
            try:
                return card.find_element(by, selector)
            except Exception:
                continue
        return None

    @staticmethod
    def _safe_text(card, selector: str) -> str:
        selectors = [part.strip() for part in selector.split(",")]
        for sel in selectors:
            try:
                elem = card.find_element(By.CSS_SELECTOR, sel)
                return elem.text.strip()
            except Exception:
                continue
        return ""

    @staticmethod
    def _is_role_company_match(title: str, role: str, company: str) -> bool:
        """Strict role match: title must contain the queried role phrase (case-insensitive).

        Example: query "data scientist" matches "Senior Data Scientist" or "Data Science Lead";
        does not match "ML Engineer" or "AI Scientist" when "data scientist" is the query.
        Company presence is not enforced because cards may omit it in the subtitle.
        """
        if not title or not role:
            return False
        title_l = title.lower()
        role_l = role.lower().strip()

        # Accept direct phrase hit or a light variant where "scientist" → "science" to allow
        # titles like "Director of Data Science" for the "data scientist" query.
        variants = {role_l}
        if "scientist" in role_l:
            variants.add(role_l.replace("scientist", "science"))
        return any(v and v in title_l for v in variants)

    @staticmethod
    def _extract_connection_status(card) -> str:
        selectors = [
            "span.entity-result__badge-text",
            "span.entity-result__badge",
            "span[data-test-entity-result-badge], span[class*='entity-result__badge']",
            "span.artdeco-entity-lockup__subtitle",
        ]
        for selector in selectors:
            try:
                elem = card.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip()
                if text:
                    return text
            except Exception:
                continue
        return ""

    def _safe_get(self, url: str, retries: int = 2, delay: float = 2.0) -> bool:
        for attempt in range(retries):
            try:
                self.driver.get(url)
                return True
            except Exception as exc:
                self.logger.debug(
                    f"[PEOPLE_SEARCH] Nav attempt {attempt + 1}/{retries} failed for {url}: {exc}"
                )
                time.sleep(delay)
        return False
