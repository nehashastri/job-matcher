"""LinkedIn connection requester for Phase 6 networking (no notes/messages)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ConnectionRequester:
    """Send connection requests or messages while staying on the search tab."""

    def __init__(
        self, driver, wait: WebDriverWait, logger: logging.Logger | None = None
    ):
        self.driver = driver
        self.wait = wait
        self.logger = logger or logging.getLogger(__name__)
        try:
            self.primary_handle = driver.current_window_handle
        except Exception:
            self.primary_handle = None

    # Navigation (self.driver.get or window switching) is only allowed within connect_matches and connect_non_matches.
    # All other functions must not perform navigation to profile URLs.

    def connect_matches(
        self,
        matches: list[dict[str, str]],
        delay_range: tuple[float, float] = (1.0, 2.0),
    ) -> None:
        """
        For each matched profile, visit the profile URL, click connect, handle 'Send without note' dialog, log actions, and close tab.
        """
        for profile in matches:
            url = profile.get("profile_url", "")
            name = profile.get("name", "")
            if not url:
                self.logger.info(
                    f"[CONNECT_MATCH] No profile_url for {name}, skipping."
                )
                continue
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            new_handle = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_handle)
            time.sleep(1)
            try:
                connect_btn = self._find_connect_button_on_profile()
                if connect_btn:
                    connect_btn.click()
                    time.sleep(1)
                    try:
                        modal = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "div.artdeco-modal.send-invite[role='dialog']",
                        )
                        if modal:
                            self.logger.info(
                                f"[CONNECT_MATCH] Connect modal detected for {name}"
                            )
                    except Exception:
                        pass
                    if self._send_invite():
                        self.logger.info(
                            f"[CONNECT_MATCH] 'Send without a note' button clicked for {name}"
                        )
                    else:
                        if self._close_connect_modal():
                            self.logger.info(
                                f"[CONNECT_MATCH] Connect modal closed for {name} (no send)"
                            )
                        else:
                            self.logger.info(
                                f"[CONNECT_MATCH] Connect modal could not be closed for {name}"
                            )
                else:
                    self.logger.info(f"[CONNECT_MATCH] No connect button for {name}")
            except Exception as exc:
                self.logger.error(f"[CONNECT_MATCH] Error for {name}: {exc}")
            finally:
                self.driver.close()
                self.driver.switch_to.window(self.primary_handle)
            self._random_delay(*delay_range)

    def connect_non_matches(
        self,
        non_matches: list[dict[str, str]],
        delay_range: tuple[float, float] = (1.0, 2.0),
    ) -> None:
        """
        For each non-matched profile, visit the profile URL, click connect, handle 'Send without note' dialog, log actions, and close tab.
        """
        for profile in non_matches:
            url = profile.get("profile_url", "")
            name = profile.get("name", "")
            if not url:
                self.logger.info(
                    f"[CONNECT_NON_MATCH] No profile_url for {name}, skipping."
                )
                continue
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            new_handle = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_handle)
            time.sleep(1)
            try:
                connect_btn = self._find_connect_button_on_profile()
                if connect_btn:
                    connect_btn.click()
                    time.sleep(1)
                    try:
                        modal = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "div.artdeco-modal.send-invite[role='dialog']",
                        )
                        if modal:
                            self.logger.info(
                                f"[CONNECT_NON_MATCH] Connect modal detected for {name}"
                            )
                    except Exception:
                        pass
                    if self._send_invite():
                        self.logger.info(
                            f"[CONNECT_NON_MATCH] 'Send without a note' button clicked for {name}"
                        )
                    else:
                        if self._close_connect_modal():
                            self.logger.info(
                                f"[CONNECT_NON_MATCH] Connect modal closed for {name} (no send)"
                            )
                        else:
                            self.logger.info(
                                f"[CONNECT_NON_MATCH] Connect modal could not be closed for {name}"
                            )
                else:
                    self.logger.info(
                        f"[CONNECT_NON_MATCH] No connect button for {name}"
                    )
            except Exception as exc:
                self.logger.error(f"[CONNECT_NON_MATCH] Error for {name}: {exc}")
            finally:
                self.driver.close()
                self.driver.switch_to.window(self.primary_handle)
            self._random_delay(*delay_range)

    def _find_connect_button_on_profile(self):
        selectors = [
            "button[aria-label*='Connect']",
            "button[data-control-name='connect']",
            "button[aria-label='Connect']",
            "button[aria-label*='Invite']",
            "button[aria-label*='connect with']",
            "button.artdeco-button--secondary",
            "a[aria-label*='Invite'][href*='search-custom-invite']",
            "a[aria-label*='Connect']",
            "a[href*='search-custom-invite']",
        ]
        for selector in selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    return btn
            except Exception:
                continue
        return None

    def llm_match_profiles(
        self,
        profiles: list[dict[str, str]],
        role_query: str,
        prompt_path: Optional[str] = None,
    ) -> dict:
        """
        Call OpenAI LLM to organize profiles into matches and non-matches.
        Stores prompt and response for traceability.
        Returns dict: {"matches": [...], "non_matches": [...], "llm_response": ...}
        """
        import json
        import os
        from datetime import datetime

        import openai

        # Load prompt template
        if prompt_path is None:
            prompt_path = os.path.join(
                os.path.dirname(__file__), "../data/LLM_base_score.txt"
            )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        # Prepare prompt
        prompt = prompt_template.format(
            role_query=role_query,
            profiles=json.dumps(profiles, ensure_ascii=False, indent=2),
        )

        # Log prompt for traceability
        log_dir = os.path.join(os.path.dirname(__file__), "../data")
        os.makedirs(log_dir, exist_ok=True)
        prompt_log_path = os.path.join(
            log_dir, f"llm_prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(prompt_log_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Call OpenAI LLM (v1.x API)
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2048,
            )
            llm_content = response.choices[0].message.content
        except Exception as exc:
            self.logger.error(f"[LLM_MATCH] OpenAI API error: {exc}")
            llm_content = "{}"

        # Log response for traceability
        llm_content = llm_content or "{}"
        response_log_path = os.path.join(
            log_dir, f"llm_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(response_log_path, "w", encoding="utf-8") as f:
            f.write(llm_content)

        # Parse LLM response
        try:
            result = json.loads(llm_content)
        except Exception as exc:
            self.logger.error(f"[LLM_MATCH] Failed to parse LLM response: {exc}")
            result = {"matches": [], "non_matches": [], "llm_response": llm_content}

        return result

    # The run_on_people_search and match logic will be replaced by LLM-based matching and connect actions.
    # Remove _handle_match, _handle_non_match, and all uses of is_role_match, match, or similar flags.

    def _handle_match(
        self,
        card,
        name: str,
        title: str,
        role: str,
        company: str,
        profile_url: str,
        store,
    ) -> tuple[str | None, str | None]:
        """Handle role matches: record message availability and connect when present."""

        message_btn = self._find_message_button_in_card(card)
        connect_btn = self._find_connect_button_in_card(card)

        message_available = bool(message_btn)
        connected = False

        if message_available:
            self.logger.info("[CONNECT] Match: message available for %s", name)
            # Only log, do not click message button

        if connect_btn:
            try:
                connect_btn.click()
                # After clicking connect, check for modal dialog
                try:
                    modal = self.driver.find_element(
                        By.CSS_SELECTOR, "div.artdeco-modal.send-invite[role='dialog']"
                    )
                    if modal:
                        self.logger.info(
                            "[CONNECT] Match: connect modal detected for %s", name
                        )
                except Exception:
                    pass
                # After clicking connect, try to click 'Send without a note'.
                if self._send_invite():
                    self.logger.info(
                        "[CONNECT] Match: 'Send without a note' button clicked for %s",
                        name,
                    )
                    connected = True
                    self.logger.info("[CONNECT] Match: connect clicked for %s", name)
                else:
                    # If 'Send without a note' not found, try to close the modal
                    if self._close_connect_modal():
                        self.logger.info(
                            "[CONNECT] Match: connect modal closed for %s (no send)",
                            name,
                        )
                    else:
                        self.logger.info(
                            "[CONNECT] Match: connect modal could not be closed for %s",
                            name,
                        )
            except Exception as exc:
                self.logger.debug(
                    f"[CONNECT] Could not click connect for {name}: {exc}"
                )
        else:
            self.logger.info(
                "[CONNECT] Match: no connect button for %s (skipping connect)", name
            )

        self._record_connection(
            store,
            name,
            title,
            profile_url,
            role,
            company,
            is_match=True,
            message_available=message_available,
            connected=connected,
            status="ConnectClickedMatch" if connected else "MessageAvailableOnly",
        )

        handled = "connect_clicked_match" if connected else None
        message_result = "message_available" if message_available else None
        # Remove misplaced code block and ensure correct return type
        return handled, message_result

    def _handle_non_match(
        self,
        card,
        name: str,
        title: str,
        role: str,
        company: str,
        profile_url: str,
        store,
    ) -> tuple[str | None, str | None]:
        message_btn = self._find_message_button_in_card(card)
        connect_btn = self._find_connect_button_in_card(card)
        if message_btn:
            self.logger.info("[CONNECT] Non-match: message available for %s", name)
            # Only log, do not click message button
        if connect_btn:
            try:
                connect_btn.click()
                # After clicking connect, check for modal dialog
                try:
                    modal = self.driver.find_element(
                        By.CSS_SELECTOR, "div.artdeco-modal.send-invite[role='dialog']"
                    )
                    if modal:
                        self.logger.info(
                            "[CONNECT] Non-match: connect modal detected for %s", name
                        )
                except Exception:
                    pass
                # After clicking connect, try to click 'Send without a note'.
                connected = False
                if self._send_invite():
                    self.logger.info(
                        "[CONNECT] Non-match: 'Send without a note' button clicked for %s",
                        name,
                    )
                    connected = True
                else:
                    # If 'Send without a note' not found, try to close the modal
                    if self._close_connect_modal():
                        self.logger.info(
                            "[CONNECT] Non-match: connect modal closed for %s (no send)",
                            name,
                        )
                    else:
                        self.logger.info(
                            "[CONNECT] Non-match: connect modal could not be closed for %s",
                            name,
                        )
                self.logger.info("[CONNECT] Non-match: connect clicked for %s", name)
                self._record_connection(
                    store,
                    name,
                    title,
                    profile_url,
                    role,
                    company,
                    is_match=False,
                    message_available=False,
                    connected=connected,
                    status="ConnectClickedNonMatch"
                    if connected
                    else "ConnectModalClosedNonMatch",
                )
                return "connect_clicked_non_match", None
            except Exception as exc:
                self.logger.debug(
                    f"[CONNECT] Could not click connect for {name}: {exc}"
                )
                return None, None
        else:
            # Visibility/logging when no connect action was taken
            self.logger.info(
                "[CONNECT] Non-match: no connect button for %s (skipping)", name
            )
            return None, None

    def _close_connect_modal(self) -> bool:
        """Try to close the LinkedIn connect modal if present."""
        try:
            # Look for the close/dismiss button in the modal
            selectors = [
                "button.artdeco-modal__dismiss",
                "button[aria-label='Dismiss']",
                "button[data-test-modal-close-btn]",
            ]
            for selector in selectors:
                try:
                    btn = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    btn.click()
                    return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _should_ignore_profile(self, profile: dict[str, Any]) -> bool:
        name = (profile.get("name") or "").strip().lower()
        if not name:
            return True
        if "lewei zeng" in name:
            return True
        return False

    def _find_message_button_in_card(self, card):
        logger = getattr(self, "logger", logging.getLogger(__name__))
        selectors = [
            "button[aria-label*='Message']",
            "a[aria-label*='Message']",
            "button[data-control-name='message']",
        ]
        # First pass: direct selectors
        for selector in selectors:
            try:
                btn = card.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    logger.info(
                        "[MESSAGE] Button detected in card via selector: %s", selector
                    )
                    return btn
            except Exception:
                continue
        # Second pass: scan for visible text or aria-label containing 'message'
        try:
            candidates = card.find_elements(By.CSS_SELECTOR, "button, a, span, div")
            for c in candidates:
                try:
                    label = (c.get_attribute("aria-label") or "").lower()
                    text = (c.text or "").lower()
                    if ("message" in label or "message" in text) and c.is_enabled():
                        logger.info(
                            "[MESSAGE] Button detected in card via candidate scan"
                        )
                        return c
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _find_connect_button_in_card(self, card):
        logger = getattr(self, "logger", logging.getLogger(__name__))
        selectors = [
            "button[aria-label*='Connect']",
            "button[data-control-name='connect']",
            "button[aria-label='Connect']",
            "button[aria-label*='Invite']",
            "button[aria-label*='connect with']",
            "button.artdeco-button--secondary",
            "a[aria-label*='Invite'][href*='search-custom-invite']",
            "a[aria-label*='Connect']",
            "a[href*='search-custom-invite']",
        ]

        # First pass: direct selectors
        for selector in selectors:
            try:
                btn = card.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    logger.info(
                        "[CONNECT] Button detected in card via selector: %s", selector
                    )
                    return btn
            except Exception:
                continue

        # Second pass: scan any buttons/links/spans/divs with visible text or label containing "connect" or "invite"
        try:
            candidates = card.find_elements(By.CSS_SELECTOR, "button, a, span, div")
            for c in candidates:
                try:
                    label = (c.get_attribute("aria-label") or "").lower()
                    text = (c.text or "").lower()
                    href = (c.get_attribute("href") or "").lower()
                    if (
                        (
                            "connect" in label
                            or "invite" in label
                            or "connect" in text
                            or "invite" in text
                        )
                        or ("search-custom-invite" in href)
                    ) and c.is_enabled():
                        logger.info(
                            "[CONNECT] Button detected in card via candidate scan"
                        )
                        return c
                except Exception:
                    continue
        except Exception:
            pass

        return None

    def _find_card_by_name(self, name: str):
        try:
            if not name:
                return None
            # No-op: was _switch_to_primary_window, not needed
            name_l = name.lower()
            xpath = (
                "//*[contains(@data-view-name,'people-search-result') or "
                "contains(@class,'reusable-search__result-container') or "
                "contains(@class,'search-result__occluded-item') or "
                "contains(@class,'entity-result')]"
                "[.//span[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), \""
                + name_l
                + "\")] or .//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), \""
                + name_l
                + '")]]'
            )
            return self.driver.find_element(By.XPATH, xpath)
        except Exception:
            return None

    def _send_invite(self) -> bool:
        selectors = [
            "button[aria-label='Send now']",
            "button[aria-label='Send']",
            "button[aria-label*='Send invitation']",
            "button[aria-label*='Send without a note']",
            "button[aria-label*='Send without note']",
            "button[data-control-name='invite_dialog_send']",
            "button[data-control-name='invite']",
        ]
        for selector in selectors:
            try:
                send_btn = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                send_btn.click()
                return True
            except Exception:
                continue
        return False

    def _wait_for_composer(self, timeout: float = 10.0):
        composer_selectors = [
            "div.msg-overlay-conversation-bubble",
            "section.msg-overlay-conversation-bubble",
            "div.msg-overlay-conversation-bubble--is-active",
            "section.msg-overlay-conversation-bubble--is-active",
            "form.msg-form",
            "div.msg-form__contenteditable",
            "div[contenteditable='true'][role='textbox']",
            "div.msg-form__container",
            "div.msg-overlay-list-bubble",
            "div.msg-overlay-conversation-bubble__content",
            "div.msg-form__textarea",
            "main.msg-conversation-container",
            "div.msg-conversation-container",
            "div.msg-compose-form__container",
            "div.msg-conversations-container",
            "div[role='dialog'][aria-label*='Message']",
            "div[aria-label*='Messaging']",
        ]
        end_time = time.time() + timeout
        while time.time() < end_time:
            for selector in composer_selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    visible = [e for e in elems if e.is_displayed()]
                    if visible:
                        return visible[0]
                except Exception:
                    continue
            time.sleep(0.3)
        return None

    def _find_card_by_url(self, profile_url: str):
        try:
            if not profile_url:
                return None
            # No-op: was _switch_to_primary_window, not needed
            profile_id = profile_url.split("/")[-1].split("?")[0]
            xpath = (
                "//a[contains(@href, '"
                + profile_id
                + "')]/ancestor::*[contains(@data-view-name,'people-search-result') "
                "or contains(@class,'reusable-search__result-container') or contains(@class,'search-result__occluded-item') "
                "or contains(@class,'entity-result')][1]"
            )
            return self.driver.find_element(By.XPATH, xpath)
        except Exception:
            return None

    def _record_connection(
        self,
        store,
        name: str,
        title: str,
        profile_url: str,
        role: str,
        company: str,
        is_match: bool,
        message_available: bool,
        connected: bool,
        status: str,
    ) -> None:
        if not store:
            return
        try:
            store.add_linkedin_connection(
                {
                    "name": name,
                    "title": title,
                    "url": profile_url,
                    "company": company,
                    "role": role,
                    "country": "",
                    "role_match": is_match,
                    "message_available": message_available,
                    "connected": connected,
                    "status": status,
                }
            )
        except Exception:
            self.logger.debug("[CONNECT] Failed to record connection")

    def _random_delay(self, min_delay: float, max_delay: float) -> None:
        try:
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
        except Exception:
            time.sleep(1)

    def _open_networking_tab(self):
        try:
            if not self.driver:
                return None
            existing = set(getattr(self.driver, "window_handles", []))
            self.driver.execute_script("window.open('about:blank','_blank');")
            time.sleep(0.5)
            handles = set(getattr(self.driver, "window_handles", []))
            new_handles = list(handles - existing)
            handle = new_handles[-1] if new_handles else None
            if handle:
                self.driver.switch_to.window(handle)
            return handle
        except Exception as exc:
            self.logger.debug(f"[CONNECT] Could not open networking tab: {exc}")
            return None

    def _close_networking_tab(self, handle, fallback) -> None:
        try:
            if (
                self.driver
                and handle
                and handle in getattr(self.driver, "window_handles", [])
            ):
                self.driver.switch_to.window(handle)
                self.driver.close()
        except Exception:
            pass
        finally:
            # Switch back to fallback or primary_handle if possible
            target = fallback or getattr(self, "primary_handle", None)
            if target:
                try:
                    self.driver.switch_to.window(target)
                except Exception:
                    pass
