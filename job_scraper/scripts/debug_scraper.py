"""
Quick debugging script to save LinkedIn page HTML
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from auth.linkedin_auth import LinkedInAuth
from auth.session_manager import SessionManager
from config.config import Config
from scraping.search_builder import LinkedInSearchBuilder

config = Config()
headless = os.getenv("HEADLESS", "true").lower() == "true"
session_manager = SessionManager(headless=headless)

try:
    driver = session_manager.start()
    auth = LinkedInAuth(session_manager)
    auth.login(config.linkedin_email, config.linkedin_password)

    # Build search URL
    test_role = {
        "title": "Software Engineer",
        "location": "United States",
        "experience_levels": ["Entry level"],
        "remote": True,
    }
    builder = LinkedInSearchBuilder()
    search_url = builder.build_role_search_url(test_role, {"date_posted": "r86400"})

    print(f"Navigating to: {search_url}")
    driver.get(search_url)

    import time

    time.sleep(10)  # Wait for page to load

    # Save the HTML near this script to avoid polluting root
    html = driver.page_source
    output_path = Path(__file__).resolve().parent / "debug_page.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"Saved page HTML to {output_path}")

    # Find job cards
    from selenium.webdriver.common.by import By

    cards = driver.find_elements(By.CLASS_NAME, "job-card-container")
    print(f"Found {len(cards)} job-card-container elements")

    if cards:
        print("\nFirst card HTML (first 500 chars):")
        print(cards[0].get_attribute("outerHTML")[:500])

        # Try to find link
        links = cards[0].find_elements(By.TAG_NAME, "a")
        print(f"\nFound {len(links)} <a> tags in first card")
        if links:
            for i, link in enumerate(links[:3]):
                href = link.get_attribute("href")
                text = link.text[:50] if link.text else ""
                print(f"  Link {i + 1}: {href} | Text: {text}")

    input("\nPress Enter to close browser...")

finally:
    session_manager.quit()
