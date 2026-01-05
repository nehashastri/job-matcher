"""LinkedIn connection requester for Phase 6 networking (no notes/messages)."""

import random
import time
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


class ConnectionRequester:
    def __init__(self, driver, wait, logger=None):
        import logging

        self.driver = driver
        self.wait = wait
        self.logger = logger or logging.getLogger(__name__)

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
