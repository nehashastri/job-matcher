"""
Test script to verify viewed job detection
This will click on jobs to mark them as viewed, then re-scrape to check detection
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from selenium.webdriver.common.by import By

from auth.linkedin_auth import LinkedInAuth
from auth.session_manager import SessionManager
from config.config import Config
from config.logging_utils import get_logger
from scraping.job_list_scraper import JobListScraper
from scraping.search_builder import LinkedInSearchBuilder

logger = get_logger(__name__)

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

    logger.info(f"Navigating to: {search_url}")
    driver.get(search_url)
    time.sleep(8)

    # Initial scrape
    logger.info("\n" + "=" * 80)
    logger.info("INITIAL SCRAPE - Before clicking any jobs")
    logger.info("=" * 80)

    list_scraper = JobListScraper(driver, config)
    jobs_before = list_scraper._scrape_current_page()

    logger.info(f"\nFound {len(jobs_before)} jobs initially:")
    for i, job in enumerate(jobs_before[:5], 1):
        viewed_icon = "✓" if job["is_viewed"] else "○"
        indicator = job.get("viewed_indicator", "none")
        logger.info(f"{i}. {viewed_icon} {job['title'][:50]}")
        logger.info(f"   ID: {job['job_id']}, Viewed: {job['is_viewed']}, Indicator: {indicator}")

    # Click on the first job to mark it as viewed
    if jobs_before:
        first_job_id = jobs_before[0]["job_id"]
        logger.info("\n" + "=" * 80)
        logger.info(f"CLICKING on first job (ID: {first_job_id}) to mark it as viewed...")
        logger.info("=" * 80)

        try:
            # Find and click the job card
            cards = driver.find_elements(By.CLASS_NAME, "job-card-container")
            if cards:
                first_card = cards[0]

                # Log classes BEFORE click
                classes_before = first_card.get_attribute("class")
                aria_before = first_card.get_attribute("aria-current")

                logger.info("BEFORE click:")
                logger.info(f"  Classes: {classes_before}")
                logger.info(f"  aria-current: {aria_before}")

                # Click the card
                first_card.click()
                time.sleep(3)  # Wait for LinkedIn to update the UI

                # Log classes AFTER click
                classes_after = first_card.get_attribute("class")
                aria_after = first_card.get_attribute("aria-current")

                logger.info("\nAFTER click:")
                logger.info(f"  Classes: {classes_after}")
                logger.info(f"  aria-current: {aria_after}")

                # Highlight what changed
                if classes_before != classes_after:
                    logger.info("\n✓ CLASSES CHANGED!")
                    added = set(classes_after.split()) - set(classes_before.split())
                    removed = set(classes_before.split()) - set(classes_after.split())
                    if added:
                        logger.info(f"  Added: {added}")
                    if removed:
                        logger.info(f"  Removed: {removed}")

                if aria_before != aria_after:
                    logger.info(f"\n✓ ARIA-CURRENT CHANGED: {aria_before} -> {aria_after}")

        except Exception as e:
            logger.error(f"Error clicking job: {e}")

    # Re-scrape to see if viewed status changed
    logger.info("\n" + "=" * 80)
    logger.info("RE-SCRAPE - After clicking first job")
    logger.info("=" * 80)

    jobs_after = list_scraper._scrape_current_page()

    logger.info(f"\nFound {len(jobs_after)} jobs after click:")
    for i, job in enumerate(jobs_after[:5], 1):
        viewed_icon = "✓" if job["is_viewed"] else "○"
        indicator = job.get("viewed_indicator", "none")

        # Check if this job's status changed
        before_job = next((j for j in jobs_before if j["job_id"] == job["job_id"]), None)
        status_changed = ""
        if before_job and before_job["is_viewed"] != job["is_viewed"]:
            status_changed = " ← STATUS CHANGED!"

        logger.info(f"{i}. {viewed_icon} {job['title'][:50]}{status_changed}")
        logger.info(f"   ID: {job['job_id']}, Viewed: {job['is_viewed']}, Indicator: {indicator}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    viewed_before = sum(1 for j in jobs_before if j["is_viewed"])
    viewed_after = sum(1 for j in jobs_after if j["is_viewed"])

    logger.info(f"Viewed jobs BEFORE: {viewed_before}/{len(jobs_before)}")
    logger.info(f"Viewed jobs AFTER:  {viewed_after}/{len(jobs_after)}")

    if viewed_after > viewed_before:
        logger.info(
            f"\n✓ Successfully detected {viewed_after - viewed_before} newly viewed job(s)!"
        )
    elif viewed_after == viewed_before == 0:
        logger.warning("\n⚠ No viewed jobs detected. LinkedIn may use a different indicator.")
        logger.info("Check the classes changes logged above.")
    else:
        logger.info("\nNo change in viewed job count.")

    input("\n\nPress Enter to close browser and exit...")

finally:
    try:
        session_manager.quit()
    except Exception:
        pass
