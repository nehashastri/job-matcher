"""
Demo script to test Connect/Message button detection and pagination for 'ai engineer at meta' on LinkedIn.
This script will:
- Log in to LinkedIn (credentials required via environment variables or prompt)
- Search for 'ai engineer at meta' in People
- For each profile card on the first N pages:
    - Count and print how many Connect and Message buttons are detected
    - Attempt to navigate to the next page and report success

WARNING: Use at your own risk. This script automates LinkedIn and may violate their TOS.
"""

import os
import time

from networking.connection_requester import ConnectionRequester
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL") or input("LinkedIn email: ")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD") or input("LinkedIn password: ")

SEARCH_QUERY = "ai engineer at meta"
MAX_PAGES = 2


# --- LinkedIn login and search helpers ---
def linkedin_login(driver, wait):
    driver.get("https://www.linkedin.com/login")
    wait.until(EC.presence_of_element_located((By.ID, "username")))
    driver.find_element(By.ID, "username").send_keys(LINKEDIN_EMAIL)
    driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    wait.until(EC.presence_of_element_located((By.ID, "global-nav-search")))
    print("Logged in!")


def go_to_people_search(driver, wait, query):
    driver.get(
        f"https://www.linkedin.com/search/results/people/?keywords={query.replace(' ', '%20')}"
    )
    try:
        wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "div.search-results-container, ul.reusable-search__entity-result-list",
                )
            )
        )
        print(f"Loaded search results for: {query}")
    except Exception:
        print(
            "Timeout waiting for people search results. Dumping HTML for inspection..."
        )
        with open("linkedin_people_search_dump.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(
            "HTML dumped to linkedin_people_search_dump.html. Browser will remain open for manual inspection."
        )
        import pdb

        pdb.set_trace()


# --- Demo main ---
def main():
    driver = webdriver.Chrome()
    import os

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL") or input("LinkedIn email: ")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD") or input("LinkedIn password: ")

    SEARCH_QUERY = "ai engineer at meta"
    MAX_PAGES = 2

    def linkedin_login(driver, wait):
        driver.get("https://www.linkedin.com/login")
        wait.until(EC.presence_of_element_located((By.ID, "username")))
        driver.find_element(By.ID, "username").send_keys(LINKEDIN_EMAIL)
        driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        wait.until(EC.presence_of_element_located((By.ID, "global-nav-search")))
        print("Logged in!")

    def go_to_people_search(driver, wait, query):
        driver.get(
            f"https://www.linkedin.com/search/results/people/?keywords={query.replace(' ', '%20')}"
        )
        try:
            wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "div.search-results-container, ul.reusable-search__entity-result-list",
                    )
                )
            )
            print(f"Loaded search results for: {query}")
        except Exception:
            print(
                "Timeout waiting for people search results. Dumping HTML for inspection..."
            )
            with open("linkedin_people_search_dump.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(
                "HTML dumped to linkedin_people_search_dump.html. Browser will remain open for manual inspection."
            )
            import pdb

            pdb.set_trace()

    def get_people_cards(driver):
        # Use the same selectors as ConnectionRequester would expect
        selectors = [
            "div.entity-result",
            "li.reusable-search__result-container",
            "div.search-result__occluded-item",
            "div.search-result__wrapper",
            "div.search-result",
            "div.artdeco-list__item",
        ]
        cards = []
        print("[INFO] Looking for people cards using selectors:")
        for selector in selectors:
            print(f"  - {selector}")
            found = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"    Found {len(found)} cards with selector '{selector}'")
            cards.extend([c for c in found if c not in cards])
        print(f"[INFO] Total unique people cards found: {len(cards)}")
        return cards

    def main():
        print("[STEP] Starting Chrome WebDriver...")
        try:
            driver = webdriver.Chrome()
            print("[STEP] Chrome WebDriver started.")
            wait = WebDriverWait(driver, 15)
            print("[STEP] Logging in to LinkedIn...")
            linkedin_login(driver, wait)
            print("[STEP] Logged in. Navigating to people search...")
            go_to_people_search(driver, wait, SEARCH_QUERY)
            print("[STEP] On people search page. Initializing ConnectionRequester...")
            requester = ConnectionRequester(driver, wait)

            connect_count = 0
            message_count = 0
            page = 1
            while page <= MAX_PAGES:
                print(f"\n--- Page {page} ---")
                cards = get_people_cards(driver)
                print(f"[INFO] Scraping {len(cards)} profile cards on page {page}")
                for idx, card in enumerate(cards):
                    print(f"[INFO] Checking card {idx + 1}/{len(cards)}")
                    connect_btn = requester._find_connect_button_in_card(card)
                    message_btn = requester._find_message_button_in_card(card)
                    if connect_btn:
                        connect_count += 1
                        print(f"  [DETECT] Card {idx + 1}: Connect button detected")
                    else:
                        print(f"  [DETECT] Card {idx + 1}: No Connect button detected")
                    if message_btn:
                        message_count += 1
                        print(f"  [DETECT] Card {idx + 1}: Message button detected")
                    else:
                        print(f"  [DETECT] Card {idx + 1}: No Message button detected")
                # Try to go to next page
                try:
                    next_btn = driver.find_element(
                        By.CSS_SELECTOR,
                        "button[aria-label*='Next'], button.artdeco-pagination__button--next",
                    )
                    if next_btn.is_enabled():
                        print("[INFO] Navigating to next page...")
                        next_btn.click()
                        time.sleep(3)
                        page += 1
                        continue
                except Exception:
                    print("[INFO] No next page button found or not clickable.")
                break
            print(f"\n[RESULT] Total Connect buttons detected: {connect_count}")
            print(f"[RESULT] Total Message buttons detected: {message_count}")
            driver.quit()
        except Exception as e:
            print(f"[ERROR] Exception occurred: {e}")
            import traceback

            traceback.print_exc()

    if __name__ == "__main__":
        main()
