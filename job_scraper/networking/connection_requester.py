"""LinkedIn connection requester for Phase 6 networking (no notes/messages)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

    def run_on_people_search(
        self,
        people_finder,
        role: str,
        company: str,
        delay_range: tuple[float, float] = (1.0, 2.0),
        store=None,
        max_pages: int | None = 3,
        use_new_tab: bool = False,
    ) -> dict[str, int]:
        """Process LinkedIn People results for up to `max_pages` pages.

        Behavior (Phase 6 spec):
        - For role matches: record presence of Message button (do not send) and, if
          Connect is present, click Connect and record the action.
        - For non-matches: if Connect is present, click Connect and record.
        - No notes/messages are sent in Phase 6; only actions/availability are stored.
        """

        summary = {
            "message_available": 0,
            "connect_clicked_match": 0,
            "connect_clicked_non_match": 0,
            "skipped": 0,
            "failed": 0,
            "pages_processed": 0,
        }

        original_handle = self._current_handle()
        networking_handle = self._open_networking_tab() if use_new_tab else None

        try:
            if networking_handle:
                self._switch_to_handle(networking_handle)

            for page_index, profiles in enumerate(
                people_finder.iterate_pages(role, company, pages=max_pages)
            ):
                summary["pages_processed"] += 1
                self.logger.info(
                    "[CONNECT] Page %s: processing %s profiles",
                    page_index + 1,
                    len(profiles),
                )

                for profile in profiles:
                    if self._should_ignore_profile(profile):
                        continue

                    name = (profile.get("name") or "").strip() or "there"
                    title = (profile.get("title") or "").strip()
                    profile_url = profile.get("profile_url", "")
                    is_match = bool(profile.get("is_role_match"))

                    card = self._find_card_by_url(profile_url)
                    if not card:
                        card = self._find_card_by_name(name)
                    if not card:
                        self.logger.info(
                            "[CONNECT] Skip: could not locate card for %s (url=%s)",
                            name,
                            profile_url or "missing",
                        )
                        summary["skipped"] += 1
                        continue

                    try:
                        if is_match:
                            handled, message_hit = self._handle_match(
                                card,
                                name,
                                title,
                                role,
                                company,
                                profile_url,
                                store,
                            )
                        else:
                            handled, message_hit = self._handle_non_match(
                                card,
                                name,
                                title,
                                role,
                                company,
                                profile_url,
                                store,
                            )

                        if message_hit:
                            summary["message_available"] += 1
                        if handled:
                            summary[handled] += 1
                        if not handled and not message_hit:
                            summary["skipped"] += 1
                    except Exception as exc:
                        self.logger.debug(f"[CONNECT] Error on profile '{name}': {exc}")
                        summary["failed"] += 1

                    self._random_delay(*delay_range)

        finally:
            if networking_handle:
                self._close_networking_tab(networking_handle, original_handle)
            elif original_handle:
                self._switch_to_handle(original_handle)

        return summary

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

        if connect_btn:
            try:
                connect_btn.click()
                connected = True
                self.logger.info("[CONNECT] Match: connect clicked for %s", name)
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
        connect_btn = self._find_connect_button_in_card(card)
        if connect_btn:
            try:
                connect_btn.click()
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
                    connected=True,
                    status="ConnectClickedNonMatch",
                )
                return "connect_clicked_non_match", None
            except Exception as exc:
                self.logger.debug(
                    f"[CONNECT] Could not click connect for {name}: {exc}"
                )

        # Visibility/logging when no connect action was taken
        self.logger.info(
            "[CONNECT] Non-match: no connect button for %s (skipping)", name
        )

        return None, None

    def _should_ignore_profile(self, profile: dict[str, Any]) -> bool:
        name = (profile.get("name") or "").strip().lower()
        if not name:
            return True
        if "lewei zeng" in name:
            return True
        return False

    def _find_message_button_in_card(self, card):
        selectors = [
            "button[aria-label*='Message']",
            "a[aria-label*='Message']",
            "button[data-control-name='message']",
        ]
        for selector in selectors:
            try:
                btn = card.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    return btn
            except Exception:
                continue
        return None

    def _find_connect_button_in_card(self, card):
        selectors = [
            "button[aria-label*='Connect']",
            "button[data-control-name='connect']",
            "button[aria-label='Connect']",
            "button[aria-label*='Invite']",
            "button[aria-label*='connect with']",
            "button.artdeco-button--secondary",
            "a[aria-label*='Invite'][href*='search-custom-invite'],",
            "a[aria-label*='Connect']",
            "a[href*='search-custom-invite']",
        ]

        # First pass: direct selectors
        for selector in selectors:
            try:
                btn = card.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    return btn
            except Exception:
                continue

        # Second pass: scan any buttons/links with visible text or label containing "connect"
        try:
            candidates = card.find_elements(By.CSS_SELECTOR, "button, a, span")
            for c in candidates:
                try:
                    label = (c.get_attribute("aria-label") or "").lower()
                    text = (c.text or "").lower()
                    href = (c.get_attribute("href") or "").lower()
                    if (
                        "connect" in label
                        or "invite" in label
                        or "connect" in text
                        or "invite" in text
                        or "search-custom-invite" in href
                    ):
                        if c.is_enabled():
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
            self._switch_to_primary_window()
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

    def _send_message(self, message_button, name: str, role: str, company: str) -> bool:
        original_handle = None
        try:
            original_handle = self.driver.current_window_handle
        except Exception:
            pass

        try:
            message_button.click()
            composer = self._wait_for_composer()
            if not composer:
                return False
            textbox = self._find_composer_textarea(composer)
            if not textbox:
                return False
            message_text = f"Hi {name}, I applied to {role} at {company} and would appreciate a quick connect."
            textbox.clear()
            textbox.send_keys(message_text)
            if not self._click_send_message():
                textbox.send_keys(Keys.ENTER)
            self._close_message_overlay()
            self._switch_to_primary_window()
            return True
        except Exception as exc:
            self.logger.info(f"[CONNECT] Could not send message: {exc}")
            self._switch_to_primary_window()
            return False
        finally:
            if original_handle:
                try:
                    self.driver.switch_to.window(original_handle)
                except Exception:
                    self._switch_to_primary_window()

    def _click_send_message(self) -> bool:
        selectors = [
            "button[aria-label='Send']",
            "button[aria-label*='Send message']",
            "button[data-control-name='send']",
            "button.msg-form__send-button",
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
        return False

    def _find_composer_textarea(self, composer):
        selectors = [
            "div[contenteditable='true'][role='textbox']",
            "div.msg-form__contenteditable",
            "div.msg-form__contenteditable p",
            "div.msg-overlay-conversation-bubble--is-active div[contenteditable='true']",
        ]
        for selector in selectors:
            try:
                elems = composer.find_elements(By.CSS_SELECTOR, selector)
                visible = [e for e in elems if e.is_displayed()]
                if visible:
                    return visible[0]
            except Exception:
                continue
        return None

    def _add_note(self, note_text: str) -> None:
        try:
            add_note_selectors = [
                "button[aria-label='Add a note']",
                "button[aria-label='Add note']",
                "button[aria-label*='Add note']",
                "button[data-control-name='invite_dialog_add_note']",
            ]
            for selector in add_note_selectors:
                try:
                    add_note_btn = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    add_note_btn.click()
                    break
                except Exception:
                    continue

            textarea_selectors = [
                "textarea",
                "textarea[name='message']",
                "textarea[id='custom-message']",
                "textarea[name='customMessage']",
                "textarea[aria-label*='Add a note']",
                "textarea[aria-label*='Note']",
            ]
            textarea = None
            for selector in textarea_selectors:
                try:
                    textarea = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if textarea:
                        break
                except Exception:
                    continue
            if not textarea:
                self.logger.info("[CONNECT] Note textarea not found")
                return
            textarea.clear()
            textarea.send_keys(note_text)
        except Exception as exc:
            self.logger.debug(f"[CONNECT] Could not add note: {exc}")

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
            self._switch_to_primary_window()
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

    def _close_message_overlay(self) -> None:
        """Close the LinkedIn messaging overlay if it is open."""
        try:
            close_selectors = [
                "button[aria-label='Dismiss']",
                "button.msg-overlay-bubble-header__control",
                "button[aria-label*='Close']",
                "button[data-control-name='overlay.close']",
            ]
            for selector in close_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        return
                except Exception:
                    continue

            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ESCAPE)
            except Exception:
                pass
        except Exception:
            self.logger.debug("[CONNECT] Could not close message overlay")

    def _switch_to_primary_window(self) -> None:
        try:
            if self.primary_handle and self.primary_handle in getattr(
                self.driver, "window_handles", []
            ):
                self.driver.switch_to.window(self.primary_handle)
                return
            handles = getattr(self.driver, "window_handles", [])
            if handles:
                self.primary_handle = handles[0]
                self.driver.switch_to.window(self.primary_handle)
        except Exception:
            pass

    def _current_handle(self):
        try:
            return self.driver.current_window_handle
        except Exception:
            return None

    def _switch_to_handle(self, handle) -> None:
        try:
            if handle:
                self.driver.switch_to.window(handle)
        except Exception:
            pass

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
            self._switch_to_handle(fallback or self.primary_handle)
