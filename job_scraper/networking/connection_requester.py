"""LinkedIn connection requester for Phase 8 networking."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

NOTE_TEMPLATE = (
    "Hi {person},\n"
    "I'm Neha, master's student at Boston University. I just applied to {role} at {company}. "
    "Would you be willing to get on a quick call? I'd like to know more about your work."
)


class ConnectionRequester:
    """Send connection requests to LinkedIn profiles with optional personalized note."""

    def __init__(
        self, driver, wait: WebDriverWait, logger: logging.Logger | None = None
    ):
        self.driver = driver
        self.wait = wait
        self.logger = logger or logging.getLogger(__name__)

    def run_on_people_search(
        self,
        people_finder,
        role: str,
        company: str,
        message_note_target: int = 10,
        no_note_target: int = 10,
        delay_range: tuple[float, float] = (1.0, 2.0),
        store=None,
        max_pages: int | None = None,
    ) -> dict[str, int]:
        """Drive the people search tab and perform outreach until quotas or exhaustion.

        Logic (strict role match only):
        - role_match=True → Message if available; else Connect with note
        - role_match=False → if Message present skip; if Connect present send without note
        - Stay in the search results tab; never open profiles
        - Stop when message+note >= target and no-note >= target, or when no more people/pages
        """

        summary = {
            "messaged": 0,
            "sent_with_note": 0,
            "sent_without_note": 0,
            "failed": 0,
            "skipped": 0,
            "pages_processed": 0,
        }

        try:
            for page_index, page_profiles in enumerate(
                people_finder.iterate_pages(role, company, pages=max_pages), start=1
            ):
                summary["pages_processed"] = page_index
                self.logger.info(
                    f"[CONNECT] Processing page {page_index} with {len(page_profiles)} profiles"
                )
                if self._process_page_profiles(
                    page_profiles,
                    role,
                    company,
                    summary,
                    delay_range,
                    store,
                    message_note_target,
                    no_note_target,
                ):
                    break  # quotas met
        except Exception as exc:
            self.logger.debug(f"[CONNECT] Failed during people search run: {exc}")

        self.logger.info(
            "[CONNECT] Completed: "
            f"messaged={summary['messaged']} | "
            f"sent_with_note={summary['sent_with_note']} | "
            f"sent_without_note={summary['sent_without_note']} | "
            f"skipped={summary['skipped']} | "
            f"failed={summary['failed']} | "
            f"pages={summary['pages_processed']}"
        )
        return summary

    def _process_page_profiles(
        self,
        profiles: list[dict[str, Any]],
        role: str,
        company: str,
        summary: dict[str, int],
        delay_range: tuple[float, float],
        store,
        message_note_target: int,
        no_note_target: int,
    ) -> bool:
        """Process all profiles on the current page. Returns True if quotas are met."""

        for idx, profile in enumerate(profiles, start=1):
            try:
                url = profile.get("profile_url", "")
                card = self._find_card_by_url(url)
                if not card:
                    self.logger.info(
                        f"[CONNECT] Card not found on page for profile idx={idx}; skipping"
                    )
                    summary["failed"] += 1
                    continue

                is_match = bool(profile.get("is_role_match"))
                person_name = profile.get("name", "").strip()
                note_text = NOTE_TEMPLATE.format(
                    person=person_name or "there",
                    role=role,
                    company=company,
                )

                if is_match:
                    self._handle_match(card, note_text, profile, role, store, summary)
                else:
                    self._handle_non_match(
                        card,
                        summary,
                        store=store,
                        profile=profile,
                        role=role,
                    )

                if self._reached_quotas(summary, message_note_target, no_note_target):
                    return True

                self._random_delay(*delay_range)
            except Exception as exc:
                self.logger.debug(f"[CONNECT] Failed on profile idx={idx}: {exc}")
                summary["failed"] += 1

        return self._reached_quotas(summary, message_note_target, no_note_target)

    def _handle_match(
        self,
        card,
        note_text: str,
        profile: dict[str, Any],
        role: str,
        store,
        summary: dict[str, int],
    ) -> None:
        msg_btn = self._find_message_button_in_card(card)
        if msg_btn:
            if self._send_message(msg_btn, note_text):
                summary["messaged"] += 1
                if store:
                    store.add_linkedin_connection(
                        {
                            "name": profile.get("name", ""),
                            "title": profile.get("title", ""),
                            "url": profile.get("profile_url", ""),
                            "role": role,
                            "country": "",
                            "message_sent": "Yes",
                            "status": "Messaged",
                        }
                    )
            else:
                self.logger.info("[CONNECT] Message send failed (card)")
                summary["failed"] += 1
            return

        connect_btn = self._find_connect_button_in_card(card)
        if connect_btn:
            try:
                connect_btn.click()
            except Exception:
                self.logger.info("[CONNECT] Connect click failed (card)")
                summary["failed"] += 1
                return

            self.logger.info(
                "[CONNECT] Match=True -> adding note before sending invite (card)"
            )
            self._add_note(note_text)
            if not self._send_invite():
                self.logger.info("[CONNECT] Send button not found (card); skipping")
                summary["failed"] += 1
                return

            summary["sent_with_note"] += 1
            if store:
                store.add_linkedin_connection(
                    {
                        "name": profile.get("name", ""),
                        "title": profile.get("title", ""),
                        "url": profile.get("profile_url", ""),
                        "role": role,
                        "country": "",
                        "message_sent": "Yes",
                        "status": "SentWithNote",
                    }
                )
            return

        self.logger.info("[CONNECT] No Message/Connect button for match; skipping")
        summary["failed"] += 1

    def _handle_non_match(
        self, card, summary: dict[str, int], store=None, profile=None, role: str = ""
    ) -> None:
        msg_btn = self._find_message_button_in_card(card)
        if msg_btn:
            self.logger.info("[CONNECT] Non-match with Message present; skipping")
            summary["skipped"] += 1
            return

        connect_btn = self._find_connect_button_in_card(card)
        if connect_btn:
            try:
                connect_btn.click()
            except Exception:
                self.logger.info("[CONNECT] Connect click failed (card, non-match)")
                summary["failed"] += 1
                return

            if not self._send_invite():
                self.logger.info("[CONNECT] Send button not found (card, non-match)")
                summary["failed"] += 1
                return

            summary["sent_without_note"] += 1
            if store and profile is not None:
                store.add_linkedin_connection(
                    {
                        "name": profile.get("name", ""),
                        "title": profile.get("title", ""),
                        "url": profile.get("profile_url", ""),
                        "role": role,
                        "country": "",
                        "message_sent": "No",
                        "status": "SentWithoutNote",
                    }
                )
            return

        self.logger.info("[CONNECT] Non-match with no Message/Connect; skipping")
        summary["skipped"] += 1

    @staticmethod
    def _reached_quotas(
        summary: dict[str, int], message_note_target: int, no_note_target: int
    ) -> bool:
        message_note_total = summary.get("messaged", 0) + summary.get(
            "sent_with_note", 0
        )
        return (
            message_note_total >= message_note_target
            and summary.get("sent_without_note", 0) >= no_note_target
        )

    def _find_message_button(self):
        selectors = [
            "button[aria-label*='Message']",
            "a[aria-label*='Message']",
            "button[data-control-name='message']",
        ]
        for selector in selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    return btn
            except Exception:
                continue
        return None

    def _find_message_button_in_card(self, card):
        selectors = [
            "a[aria-label*='Message']",
            "button[aria-label*='Message']",
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
            "button[aria-label*='Invite']",
            "a[aria-label*='Connect']",
            "a[aria-label*='Invite']",
        ]
        for selector in selectors:
            try:
                btn = card.find_element(By.CSS_SELECTOR, selector)
                if btn and btn.is_enabled():
                    return btn
            except Exception:
                continue
        return None

    def _send_message(self, msg_button, note_text: str) -> bool:
        try:
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", msg_button
                )
            except Exception:
                pass

            # Hide interop overlay that can block clicks
            try:
                self.driver.execute_script(
                    "var o=document.getElementById('interop-outlet'); if(o){o.style.visibility='hidden'; o.style.pointerEvents='none'; o.style.zIndex='0';}"
                )
            except Exception:
                pass

            href = msg_button.get_attribute("href") or ""

            clicked = False
            try:
                msg_button.click()
                clicked = True
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", msg_button)
                    clicked = True
                except Exception:
                    clicked = False

            # Wait for overlay/composer; if missing, try navigating to href in same tab
            content = self._wait_for_composer()
            if not content and href:
                try:
                    self.driver.get(href)
                    content = self._wait_for_composer()
                except Exception:
                    content = None

            if not content:
                self.logger.info("[CONNECT] Message box not found (composer)")
                return False

            try:
                content.clear() if hasattr(content, "clear") else None
            except Exception:
                pass
            content.send_keys(note_text)
            time.sleep(0.3)

            send_selectors = [
                "button.msg-form__send-button",
                "button[aria-label='Send now']",
                "button[aria-label='Send']",
            ]
            for selector in send_selectors:
                try:
                    send_btn = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    send_btn.click()
                    self.logger.info("[CONNECT] Message sent")
                    self._close_message_overlay()
                    return True
                except Exception:
                    continue
            # Fallback: send via Enter if button never appears (button may render after typing)
            try:
                content.send_keys(Keys.ENTER)
                self.logger.info("[CONNECT] Message sent via Enter fallback")
                self._close_message_overlay()
                return True
            except Exception:
                pass
            self.logger.info("[CONNECT] Send message button not found")
            return False
        except Exception as exc:
            self.logger.info(f"[CONNECT] Could not send message: {exc}")
            return False

    def _click_menu_connect(self) -> None:
        try:
            menu_selectors = ["//span[text()='Connect']", "//div[text()='Connect']"]
            for xpath in menu_selectors:
                try:
                    item = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    item.click()
                    return
                except Exception:
                    continue
        except Exception:
            pass

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

    def _close_message_overlay(self) -> None:
        try:
            close_selectors = [
                "button.msg-overlay-bubble-header__control[aria-label*='Close']",
                "button[aria-label*='Close your draft conversation']",
                "button.msg-overlay-bubble-header__control",
            ]
            for selector in close_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if btn and btn.is_displayed():
                        btn.click()
                        return
                except Exception:
                    continue
        except Exception:
            pass

    def _wait_for_composer(self):
        composer_selectors = [
            "div.msg-form__contenteditable",
            "div[contenteditable='true']",
            "form.msg-form",
            "div.msg-overlay-conversation-bubble",
        ]
        for selector in composer_selectors:
            try:
                elem = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if elem:
                    return elem
            except Exception:
                continue
        return None

    def _find_card_by_url(self, profile_url: str):
        try:
            if not profile_url:
                return None
            profile_id = profile_url.split("/")[-1].split("?")[0]
            xpath = f"//a[contains(@href, '{profile_id}')]/ancestor::*[contains(@data-view-name,'people-search-result') or contains(@class,'reusable-search__result-container') or contains(@class,'search-result__occluded-item') or contains(@class,'entity-result')][1]"
            return self.driver.find_element(By.XPATH, xpath)
        except Exception:
            return None

    def _random_delay(self, min_delay: float, max_delay: float) -> None:
        try:
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
        except Exception:
            time.sleep(1)
