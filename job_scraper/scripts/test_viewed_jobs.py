"""
Test script to verify viewed job detection and skipping
This will:
1. Scrape initial jobs (all unviewed)
2. Click on first 2 jobs to mark them as viewed
3. Re-scrape to detect viewed jobs
4. Verify that viewed jobs are skipped in detail scraping
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selenium.webdriver.common.by import By

from auth.linkedin_auth import LinkedInAuth
from auth.session_manager import SessionManager
from config.config import Config
from config.logging_utils import get_logger
from scraping.job_detail_scraper import JobDetailScraper
from scraping.job_list_scraper import JobListScraper
from scraping.search_builder import LinkedInSearchBuilder

logger = get_logger(__name__)


def test_viewed_detection():
    """Test viewed job detection workflow"""

    config = Config()
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    session_manager = SessionManager(headless=headless)

    try:
        logger.info("=" * 80)
        logger.info("TEST: Viewed Job Detection")
        logger.info("=" * 80)

        # Start browser and login
        driver = session_manager.start()
        auth = LinkedInAuth(session_manager)
        auth.login(config.linkedin_email, config.linkedin_password)

        # Build search URL
        test_role = {
            "title": "Software Engineer",
            "location": "United States",
            "experience_levels": ["Entry level", "Associate", "Mid-Senior level"],
            "remote": True,
        }
        builder = LinkedInSearchBuilder()
        search_url = builder.build_role_search_url(test_role, {"date_posted": "r86400"})

        logger.info(f"\nNavigating to: {search_url}")
        driver.get(search_url)
        time.sleep(8)

        # STEP 1: Initial scrape
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Initial Scrape - Before clicking any jobs")
        logger.info("=" * 80)

        list_scraper = JobListScraper(driver, config)
        jobs_before = list_scraper._scrape_current_page()

        # Fallback: if nothing found, run full list scrape to trigger waits/scrolls
        if not jobs_before:
            logger.info("No jobs found on first pass; retrying with full list scrape")
            jobs_before = list_scraper.scrape_job_list(search_url, max_jobs=10)

        logger.info(f"\nFound {len(jobs_before)} jobs initially:")
        for i, job in enumerate(jobs_before[:5], 1):
            viewed_icon = "✓" if job["is_viewed"] else "○"
            indicator = job.get("viewed_indicator", "none")
            logger.info(f"{i}. {viewed_icon} [{job['job_id']}] {job['title'][:50]}")
            logger.info(f"   Viewed: {job['is_viewed']}, Indicator: {indicator}")

        # Count unviewed jobs before
        unviewed_before = sum(1 for j in jobs_before if not j["is_viewed"])
        logger.info(f"\nUnviewed jobs: {unviewed_before} / {len(jobs_before)}")

        if len(jobs_before) < 2:
            logger.error("Not enough jobs to test! Need at least 2 jobs.")
            return False

        # STEP 2: Click on first 2 jobs to mark them as viewed
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Clicking first 2 jobs to mark as viewed")
        logger.info("=" * 80)

        jobs_to_click = jobs_before[:2]
        for i, job in enumerate(jobs_to_click, 1):
            logger.info(f"\nClicking job {i}/2: {job['title'][:50]}")
            try:
                # Find and click the job card
                job_anchor = driver.find_element(
                    By.CSS_SELECTOR, f"a[href*='/jobs/view/{job['job_id']}']"
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", job_anchor)
                time.sleep(0.5)
                job_anchor.click()
                logger.info(f"  ✓ Clicked job {job['job_id']}")
                time.sleep(3)  # Wait for LinkedIn to update the UI

                # Capture post-click styling to identify viewed marker
                try:
                    anchor_classes = job_anchor.get_attribute("class") or ""
                    logger.info(f"  Anchor classes: {anchor_classes}")

                    container = None
                    # Try common ancestors that hold visited state
                    for xpath in [
                        "./ancestor::*[contains(@class,'job-card-container')][1]",
                        "./ancestor::*[contains(@class,'jobs-search-results__list-item')][1]",
                        "./ancestor::li[1]",
                        "./ancestor::div[1]",
                    ]:
                        try:
                            container = job_anchor.find_element(By.XPATH, xpath)
                            if container:
                                break
                        except Exception:
                            continue

                    if container:
                        container_classes = container.get_attribute("class") or ""
                        container_text = (container.text or "").strip().replace("\n", " ")
                        logger.info(f"  Container classes: {container_classes}")
                        if container_text:
                            logger.info(f"  Container text: {container_text}")
                    else:
                        logger.warning("  Could not locate a container ancestor for styling probe")
                except Exception as e:
                    logger.warning(f"  Could not check post-click attributes: {e}")

            except Exception as e:
                logger.error(f"  ✗ Failed to click job {job['job_id']}: {e}")

        # STEP 3: Re-scrape to detect viewed jobs
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Re-scraping to detect viewed jobs")
        logger.info("=" * 80)

        # Scroll to top to reload the list
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        jobs_after = list_scraper._scrape_current_page()

        logger.info(f"\nFound {len(jobs_after)} jobs after clicking:")
        for i, job in enumerate(jobs_after[:5], 1):
            viewed_icon = "✓" if job["is_viewed"] else "○"
            indicator = job.get("viewed_indicator", "none")
            logger.info(f"{i}. {viewed_icon} [{job['job_id']}] {job['title'][:50]}")
            logger.info(f"   Viewed: {job['is_viewed']}, Indicator: {indicator}")

        # Count unviewed jobs after
        unviewed_after = sum(1 for j in jobs_after if not j["is_viewed"])
        logger.info(f"\nUnviewed jobs: {unviewed_after} / {len(jobs_after)}")

        # STEP 4: Compare results
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Analysis - Did clicking mark jobs as viewed?")
        logger.info("=" * 80)

        # Check if the clicked jobs are now marked as viewed
        clicked_job_ids = {job["job_id"] for job in jobs_to_click}
        detected_as_viewed = []
        still_unviewed = []

        for job in jobs_after:
            if job["job_id"] in clicked_job_ids:
                if job["is_viewed"]:
                    detected_as_viewed.append(job)
                else:
                    still_unviewed.append(job)

        logger.info(f"\nClicked {len(jobs_to_click)} jobs:")
        logger.info(f"  ✓ Detected as viewed: {len(detected_as_viewed)}")
        logger.info(f"  ✗ Still showing unviewed: {len(still_unviewed)}")

        if detected_as_viewed:
            logger.info("\nJobs successfully detected as viewed:")
            for job in detected_as_viewed:
                logger.info(f"  • {job['title'][:50]} (indicator: {job['viewed_indicator']})")

        if still_unviewed:
            logger.warning("\nJobs NOT detected as viewed (false negatives):")
            for job in still_unviewed:
                logger.warning(f"  • {job['title'][:50]}")

        # STEP 5: Test skip_viewed_jobs functionality
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Testing skip_viewed_jobs functionality")
        logger.info("=" * 80)

        # Scrape with skip_viewed=True
        logger.info("\nScraping with skip_viewed_jobs=True")
        config.skip_viewed_jobs = True
        jobs_filtered = list_scraper.scrape_job_list(search_url, max_jobs=5)

        logger.info(f"\nFiltered to {len(jobs_filtered)} unviewed jobs:")
        for i, job in enumerate(jobs_filtered, 1):
            logger.info(f"{i}. [{job['job_id']}] {job['title'][:50]}")
            logger.info(f"   Viewed: {job['is_viewed']}")

        # Verify all filtered jobs are unviewed
        all_unviewed = all(not job["is_viewed"] for job in jobs_filtered)
        logger.info(f"\nAll filtered jobs are unviewed: {all_unviewed}")

        # STEP 6: Test detail scraping (should skip viewed jobs)
        logger.info("\n" + "=" * 80)
        logger.info("STEP 6: Testing detail scraping with viewed job skipping")
        logger.info("=" * 80)

        # Create a mix of viewed and unviewed jobs
        test_jobs = jobs_after[:3]  # Take first 3 jobs (some may be viewed)

        logger.info(f"\nScraping details for {len(test_jobs)} jobs:")
        for job in test_jobs:
            viewed_icon = "✓" if job["is_viewed"] else "○"
            logger.info(f"  {viewed_icon} {job['title'][:50]}")

        detail_scraper = JobDetailScraper(driver, config)

        logger.info("\n--- Starting Detail Scraping ---")
        for i, job in enumerate(test_jobs, 1):
            logger.info(f"\nJob {i}/{len(test_jobs)}: {job['title'][:50]}")
            logger.info(f"  Viewed: {job['is_viewed']}")

            if config.skip_viewed_jobs and job["is_viewed"]:
                logger.info("  ⊘ Skipping (job already viewed)")
                continue

            details = detail_scraper.scrape_job_details(job["job_id"])
            if details:
                desc_len = len(details.get("description", ""))
                logger.info(f"  ✓ Scraped successfully ({desc_len} chars)")
            else:
                logger.info("  ✗ Failed to scrape details")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Initial unviewed: {unviewed_before}")
        logger.info(f"After clicking: {unviewed_after}")
        logger.info(f"Detected as viewed: {len(detected_as_viewed)} / {len(jobs_to_click)}")
        logger.info(f"Detection working: {'✓ YES' if detected_as_viewed else '✗ NO'}")

        return True

    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return False

    finally:
        # Keep browser open for inspection
        logger.info("\n--- Keeping browser open for 15 seconds ---")
        logger.info("You can inspect the LinkedIn page")
        time.sleep(15)

        logger.info("\n--- Closing Browser ---")
        session_manager.quit()


if __name__ == "__main__":
    success = test_viewed_detection()

    if success:
        print("\n✓ Test completed!")
        sys.exit(0)
    else:
        print("\n✗ Test failed")
        sys.exit(1)
