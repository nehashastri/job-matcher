from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Generator
from urllib.parse import quote_plus

from openai import OpenAI
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

"""
LinkedIn People search helper for Phase 6 networking.

Scrapes LinkedIn People cards for networking, matches profiles using LLM, and provides helper utilities for extracting text from cards.
"""


class PeopleFinder:
    """
    Helper for scraping LinkedIn People cards and matching profiles using LLM.
    """

    @staticmethod
    def safe_text(card, selector: str) -> str:
        import logging

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
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}.scrape_people_cards"
        )
        """
        Scrape LinkedIn People cards for a given role at a company.
        Returns a list of dicts with keys: name, title, profile_url, company, reason (matches only).
        Args:
            role (str): Job role to search for
            company (str): Company name
        Returns:
            list[dict[str, str]]: List of matched profiles
        """
        import os

        max_pages = int(os.getenv("MAX_PEOPLE_SEARCH_PAGES", 3))
        all_profiles: list[dict[str, str]] = []
        query = f"{role} at {company}".strip()
        try:
            for page_profiles in self.iterate_pages(role, company, pages=max_pages):
                for profile in page_profiles:
                    # Keep name, title, current_position, profile_url
                    card = {
                        "name": profile.get("name", ""),
                        "title": profile.get("title", ""),
                        "current_position": profile.get("current_position", ""),
                        "profile_url": profile.get("profile_url", ""),
                        "company": company,
                    }
                    all_profiles.append(card)
        except Exception as exc:
            self.logger.error(
                f"[PEOPLE_SEARCH] Error during scrape_people_cards: {exc}"
            )
        # Batch LLM call for all profiles
        matches = self._llm_batch_profile_match(all_profiles, query)
        return matches

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
                prompt = f.read().strip()
        except Exception:
            prompt = (
                "You are given a list of LinkedIn profile cards, each with: name, title, current_position, profile_url. "
                "You are also given the original search query (role at company). "
                "For each profile, decide if this person is a match for the search query, using BOTH the title and current_position fields. "
                'Return JSON only: {"matches": [ {"name": ..., "title": ..., "current_position": ..., "profile_url": ..., "company": ..., "is_match": true, "reason": "..."}, ... ]}. '
                'Only include profiles in the "matches" list if their title or current_position clearly matches the role in the query. Otherwise, exclude them. '
                "Do not return non-matches. For each match, include all columns: name, title, current_position, profile_url, company, and reason."
            )
        # Prepare LLM input
        profiles_json = json.dumps(profiles, ensure_ascii=False)
        from openai.types.chat import (
            ChatCompletionSystemMessageParam,
            ChatCompletionUserMessageParam,
        )

        messages: list[
            ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam
        ] = [
            ChatCompletionSystemMessageParam(role="system", content=str(prompt)),
            ChatCompletionUserMessageParam(
                role="user", content=str(f"Query: {query}\nProfiles: {profiles_json}")
            ),
        ]
        # Use OpenAI client (assume API key in env/config)
        api_key = getattr(self, "openai_api_key", None) or os.getenv(
            "OPENAI_API_KEY", ""
        )
        if not api_key:
            self.logger.error("No OpenAI API key configured for LLM profile match.")
            return []
        client = OpenAI(api_key=api_key)
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content if resp.choices else "{}"
            data = json.loads(content or "{}")
            matches = data.get("matches", [])
            # LLM only returns matched profiles, so return as-is
            return [
                {
                    "name": m.get("name", ""),
                    "title": m.get("title", ""),
                    "current_position": m.get("current_position", ""),
                    "profile_url": m.get("profile_url", ""),
                    "company": m.get("company", ""),
                    "reason": m.get("reason", ""),
                }
                for m in matches
            ]
        except Exception as exc:
            self.logger.error(f"LLM batch profile match failed: {exc}")
            return []

    def __init__(
        self, driver, wait: WebDriverWait, logger: logging.Logger | None = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        self.driver = driver
        self.wait = wait
        self.base_url = "https://www.linkedin.com"

    def iterate_pages(
        self, role: str, company: str, pages: int | None = None
    ) -> Generator[list[dict[str, Any]], None, None]:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.iterate_pages")
        """Yield profiles page-by-page, opening the search in a new tab and closing it after done."""
        query = f"{role} at {company}".strip()
        search_url = (
            f"{self.base_url}/search/results/people/?keywords={quote_plus(query)}"
        )
        self.logger.info(f"[PEOPLE_SEARCH] '{query}' (new tab)")

        original_handle = self.driver.current_window_handle
        self.driver.execute_script(f"window.open('{search_url}', '_blank');")
        new_handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(new_handle)

        try:
            self._click_people_filter()
            self._ensure_people_url(search_url)
            self._wait_for_results()
            try:
                self.logger.info(
                    f"[PEOPLE_SEARCH] Current URL: {self.driver.current_url}"
                )
            except Exception:
                pass

            page_count = 0
            while True:
                self._scroll_results()
                page_profiles = self._scrape_current_page(role, company)
                for p in page_profiles:
                    self.logger.info(
                        f"[PEOPLE_SEARCH] Profile: name='{p.get('name')}', title='{p.get('title')}'"
                    )
                yield page_profiles

                page_count += 1
                if pages is not None and page_count >= pages:
                    break
                if not self._click_next_page():
                    break
                time.sleep(1)
        finally:
            # Close the search tab and switch back
            self.driver.close()
            self.driver.switch_to.window(original_handle)

    def _click_people_filter(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._click_people_filter"
        )
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

    def _click_next_page(self) -> bool:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._click_next_page"
        )
        """
        Clicks the 'Next' button on LinkedIn people search results, if present.
        Returns True if next page was clicked, False otherwise.
        """
        try:
            next_btn_selectors = [
                "button[aria-label='Next']",
                "button[aria-label='Next page']",
                "button[aria-label='Next Page']",
                "button[data-test-pagination-page-btn='next']",
            ]
            for selector in next_btn_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_enabled():
                        btn.click()
                        time.sleep(1)
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

    # Removed unused legacy function _search_via_bar

    def _scrape_current_page(self, role: str, company: str) -> list[dict[str, str]]:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._scrape_current_page"
        )
        """
        Scrape all profile cards on the current page, returning a list of profile dicts
        with direct references to card, connect button, and message button.
        """
        profiles = []
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
            "[data-view-name='people-search-result'], li.reusable-search__result-container, div.reusable-search__result-container, div.search-result__occluded_item",
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
            if profile and (
                profile["profile_url"] or profile["name"] or profile["title"]
            ):
                profiles.append(profile)
        return profiles

    def _scroll_results(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._scroll_results"
        )
        try:
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(1)
        except Exception:
            pass

    def _wait_for_results(self) -> None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._wait_for_results"
        )
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
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._dump_page")
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
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._ensure_people_url"
        )
        try:
            if "search/results/people" not in (self.driver.current_url or ""):
                self._safe_get(search_url)
        except Exception:
            self._safe_get(search_url)

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
            for label, selector in selectors.items():
                count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
                self.logger.info(f"[PEOPLE_SEARCH] Selector '{label}' count={count}")
        except Exception as exc:
            self.logger.debug(f"[PEOPLE_SEARCH] Failed counting selectors: {exc}")

    def _extract_profile(self, card, role: str, company: str) -> dict[str, str] | None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._extract_profile"
        )
        """
        Extracts minimal profile info from a LinkedIn people search card.
        Returns a dict with name, title, profile_url only.
        """
        name = ""
        profile_url = ""
        title = ""
        current_position = ""
        try:
            link_elem = card.find_element(
                By.CSS_SELECTOR, "a[data-view-name='search-result-lockup-title']"
            )
            if link_elem:
                name = link_elem.text.strip()
                profile_url = link_elem.get_attribute("href") or ""
        except Exception:
            pass
        if not profile_url:
            try:
                fallback_links = card.find_elements(
                    By.CSS_SELECTOR, "a[href*='/in/'], a[href*='miniProfileUrn']"
                )
                for link in fallback_links:
                    href = link.get_attribute("href")
                    if href:
                        profile_url = href
                        if not name:
                            name = link.text.strip()
                        break
            except Exception:
                pass
        if not name:
            name = PeopleFinder.safe_text(
                card, "span.entity-result__title-text span[aria-hidden='true']"
            )
        if not name:
            name = PeopleFinder.safe_text(card, "span[dir='ltr']")
        # Extract 'title' (headline/summary)
        try:
            # This matches the inspected element: <p class="c7ecc111 ..."> (headline/summary)
            title_elem = card.find_element(By.CSS_SELECTOR, "div._443f33b9 p.c7ecc111")
            title = title_elem.text.strip()
        except Exception:
            title = PeopleFinder.safe_text(
                card,
                "div._443f33b9 p.c7ecc111, p.c7ecc111, p[data-view-name='search-result-subtitle'], div.entity-result__primary-subtitle, div.entity-result__secondary-subtitle, p._57a34c9c._3f883ddb._0da3dbae._1ae18243",
            )

        # Extract 'current_position' (Current: ...)
        try:
            current_elem = card.find_element(By.CSS_SELECTOR, "div.bd59b9d3 p.c7ecc111")
            # Try to extract the job title and company from <strong><span class="b5f00f6b">...</span></strong>
            strong_spans = current_elem.find_elements(
                By.CSS_SELECTOR, "strong > span.b5f00f6b"
            )
            if strong_spans and len(strong_spans) >= 2:
                job_title = strong_spans[0].text.strip()
                company_name = strong_spans[1].text.strip()
                current_position = f"{job_title} at {company_name}"
            else:
                current_position = current_elem.text.strip()
        except Exception:
            current_position = ""
        if title and "mutual connection" in title.lower():
            title = ""
        if profile_url or name or title or current_position:
            return {
                "name": name,
                "title": title,
                "current_position": current_position,
                "profile_url": profile_url,
            }
        return None

    # ...existing code...

    def _safe_get(self, url: str, retries: int = 2, delay: float = 2.0) -> bool:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._safe_get")
        from utils.webdriver_utils import safe_get

        return safe_get(self.driver, self.logger, url, retries, delay)
