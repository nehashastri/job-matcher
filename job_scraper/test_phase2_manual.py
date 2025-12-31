"""
Test script for Phase 2: LinkedIn Job Scraping
Run this to see the scrapers in action with real logging
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from auth.linkedin_auth import LinkedInAuth
from auth.session_manager import SessionManager
from config.config import Config
from config.logging_utils import get_logger
from scraping.job_detail_scraper import JobDetailScraper
from scraping.job_list_scraper import JobListScraper
from scraping.search_builder import LinkedInSearchBuilder

# Set up logging
logger = get_logger(__name__)


def test_scraping():
    """Test the LinkedIn scraping workflow"""

    # Load configuration
    logger.info("=" * 80)
    logger.info("PHASE 2 TEST: LinkedIn Job Scraping")
    logger.info("=" * 80)

    config = Config()

    # Check if credentials are set
    if not config.linkedin_email or not config.linkedin_password:
        logger.error("LinkedIn credentials not found in .env file!")
        logger.error("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file")
        return False

    logger.info(f"LinkedIn Email: {config.linkedin_email}")
    logger.info(f"Max jobs per role: {config.max_jobs_per_role}")
    logger.info(f"Skip viewed jobs: {config.skip_viewed_jobs}")
    logger.info(f"Request delay: {config.request_delay_min}-{config.request_delay_max}s")

    # Initialize session manager
    logger.info("\n--- Step 1: Starting Browser Session ---")
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    session_manager = SessionManager(
        headless=headless,
        cookie_path=Path("data/.linkedin_cookies.pkl"),
    )

    try:
        driver = session_manager.start()
        logger.info("Browser started successfully")

        # Initialize LinkedIn auth
        logger.info("\n--- Step 2: Authenticating with LinkedIn ---")
        auth = LinkedInAuth(session_manager)

        success = auth.login(config.linkedin_email, config.linkedin_password)

        if not success:
            logger.error("LinkedIn authentication failed!")
            return False

        logger.info("Authentication successful!")

        # Get first enabled role from roles.json
        logger.info("\n--- Step 3: Loading Role Configuration ---")
        enabled_roles = [role for role in config.roles if role.get("enabled", False)]

        if not enabled_roles:
            logger.warning("No enabled roles found in roles.json!")
            logger.info("Testing with default role: Software Engineer")
            test_role = {
                "title": "Software Engineer",
                "location": "United States",
                "experience_levels": ["Internship", "Entry level", "Associate"],
                "remote": True,
                "enabled": True,
            }
        else:
            test_role = enabled_roles[0]
            logger.info(f"Using role: {test_role['title']}")

        # Build search URL
        logger.info("\n--- Step 4: Building Search URL ---")
        builder = LinkedInSearchBuilder()
        search_url = builder.build_role_search_url(test_role, config.search_settings)
        logger.info(f"Search URL: {search_url}")

        # Scrape job list
        logger.info("\n--- Step 5: Scraping Job List ---")
        logger.info(f"Looking for unviewed jobs (skip_viewed={config.skip_viewed_jobs})")

        list_scraper = JobListScraper(driver, config)
        jobs = list_scraper.scrape_job_list(search_url, max_jobs=5)  # Limit to 5 for testing

        logger.info(f"\n[SCRAPE_LIST] Found {len(jobs)} jobs")

        if not jobs:
            logger.warning("No jobs found! This could mean:")
            logger.warning("  - All jobs on the first page have been viewed")
            logger.warning("  - The search returned no results")
            logger.warning("  - There was an issue with the page structure")
            return False

        # Display job list
        logger.info("\n--- Job List ---")
        for i, job in enumerate(jobs, 1):
            viewed_status = "✓ VIEWED" if job["is_viewed"] else "○ NOT VIEWED"
            viewed_detail = f" ({job.get('viewed_indicator', 'no indicator')})"

            logger.info(f"{i}. [{job['job_id']}] {job['title']}")
            logger.info(f"   Company: {job['company']}")
            logger.info(f"   Location: {job['location']}")
            logger.info(f"   Status: {viewed_status}{viewed_detail if job['is_viewed'] else ''}")
            logger.info(f"   URL: {job['job_url']}")
            logger.info("")

        # Scrape details for ALL jobs (not just 2)
        logger.info("\n--- Step 6: Scraping Job Details ---")
        logger.info(f"Scraping details for all {len(jobs)} jobs...")
        detail_scraper = JobDetailScraper(driver, config)
        details_count = 0

        for i, job in enumerate(jobs, 1):  # Scrape ALL jobs
            logger.info(f"\n--- Job {i}/{len(jobs)}: {job['title']} ---")

            details = detail_scraper.scrape_job_details(job["job_id"])

            if details:
                logger.info(f"[JOB_DETAIL] Successfully scraped job {job['job_id']}")
                logger.info(f"  Description length: {len(details.get('description', ''))} chars")
                logger.info(f"  Seniority: {details.get('seniority', 'Unknown')}")
                logger.info(f"  Employment type: {details.get('employment_type', 'Unknown')}")
                logger.info(f"  Posted: {details.get('posted_time', 'Unknown')}")
                logger.info(f"  Applicants: {details.get('applicant_count', 'Unknown')}")
                logger.info(f"  Remote eligible: {details.get('remote_eligible', False)}")
                details_count += 1

                # Show FULL description
                desc = details.get("description", "")
                if desc:
                    logger.info("\n  === FULL JOB DESCRIPTION ===")
                    logger.info(f"{desc}")
                    logger.info("  === END OF DESCRIPTION ===\n")
            else:
                logger.error(f"[JOB_DETAIL] Failed to scrape job {job['job_id']}")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("SCRAPING TEST COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Jobs found: {len(jobs)}")
        logger.info(f"Jobs detailed: {details_count}")
        logger.info("Status: SUCCESS ✓")

        return True

    except Exception as e:
        logger.error(f"Error during scraping test: {e}", exc_info=True)
        return False

    finally:
        # Keep browser open for a few seconds so user can see results
        logger.info("\n--- Keeping browser open for 10 seconds ---")
        logger.info("You can inspect the LinkedIn page and see what was scraped")
        import time

        time.sleep(10)

        # Close browser
        logger.info("\n--- Closing Browser ---")
        session_manager.quit()
        logger.info("Browser closed")


if __name__ == "__main__":
    success = test_scraping()

    if success:
        print("\n✓ Test completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Test failed")
        sys.exit(1)
