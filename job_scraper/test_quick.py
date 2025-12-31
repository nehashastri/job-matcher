"""
Quick test to verify the fixes
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth.linkedin_auth import LinkedInAuth
from auth.session_manager import SessionManager
from config.config import Config
from config.logging_utils import get_logger
from scraping.job_detail_scraper import JobDetailScraper
from scraping.job_list_scraper import JobListScraper
from scraping.search_builder import LinkedInSearchBuilder

logger = get_logger(__name__)


def test_quick():
    """Quick test"""
    config = Config()
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    session_manager = SessionManager(headless=headless)

    try:
        driver = session_manager.start()
        auth = LinkedInAuth(session_manager)
        auth.login(config.linkedin_email, config.linkedin_password)

        # Build search
        builder = LinkedInSearchBuilder()
        search_url = builder.build_search_url(
            keywords="Software Engineer",
            location="United States",
            remote=True,
            experience_levels=["Entry level", "Associate"],
            date_posted="r86400",
        )

        logger.info(f"Search URL: {search_url}")

        # Scrape list
        list_scraper = JobListScraper(driver, config)
        jobs = list_scraper.scrape_job_list(search_url, max_jobs=3)

        logger.info(f"Found {len(jobs)} jobs")

        # Scrape details for first job
        if jobs:
            detail_scraper = JobDetailScraper(driver, config)
            details = detail_scraper.scrape_job_details(jobs[0]["job_id"])

            if details:
                logger.info("✓ Details scraped successfully!")
                logger.info(f"  Seniority: {details.get('seniority')}")
                logger.info(f"  Employment type: {details.get('employment_type')}")
                logger.info(f"  Posted time: {details.get('posted_time')}")
                logger.info(f"  Applicants: {details.get('applicant_count')}")
                logger.info(f"  Remote eligible: {details.get('remote_eligible')}")
                logger.info(f"  Description length: {len(details.get('description', ''))}")
                return True
            else:
                logger.error("✗ Failed to scrape details")
                return False

        return False

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return False
    finally:
        import time

        time.sleep(5)
        session_manager.quit()


if __name__ == "__main__":
    success = test_quick()
    sys.exit(0 if success else 1)
