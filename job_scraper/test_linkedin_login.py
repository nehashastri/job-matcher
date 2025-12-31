"""
Manual test script to verify LinkedIn authentication with actual credentials
Run this to test the login flow and see logs
"""

import os
from pathlib import Path

from auth.linkedin_auth import LinkedInAuth
from auth.session_manager import SessionManager
from config.config import get_config
from config.logging_utils import setup_logging

# Setup logging to see authentication flow
logger = setup_logging(
    log_dir="logs",
    log_level="INFO",
    log_file="linkedin_auth_test.log",
    enable_console=True,
)

logger.info("=" * 60)
logger.info("LinkedIn Authentication Test")
logger.info("=" * 60)

# Load config
config = get_config()

logger.info(f"LinkedIn Email: {config.linkedin_email}")
logger.info("Cookie Path: data/.linkedin_cookies.pkl")

# Create session manager
headless = os.getenv("HEADLESS", "true").lower() == "true"
session_manager = SessionManager(
    headless=headless,
    cookie_path=Path("data/.linkedin_cookies.pkl"),
)

# Create auth handler
auth = LinkedInAuth(
    session_manager=session_manager,
    max_retries=3,
    backoff_start_seconds=2,
    backoff_max_seconds=30,
)

try:
    logger.info("Attempting LinkedIn login...")
    success = auth.login(config.linkedin_email, config.linkedin_password)

    if success:
        logger.info("✓ Successfully logged into LinkedIn!")
        logger.info("✓ Cookies saved for future sessions")

        # Navigate to feed to confirm
        driver = session_manager.get_driver()
        logger.info(f"Current URL: {driver.current_url}")

        # Keep browser open for a moment
        import time

        logger.info("Keeping browser open for 5 seconds to verify...")
        time.sleep(5)
    else:
        logger.error("✗ Login failed")

except Exception as e:
    logger.error(f"✗ Authentication error: {e}", exc_info=True)

finally:
    logger.info("Closing browser session...")
    session_manager.quit()
    logger.info("=" * 60)
    logger.info("Test complete. Check logs/linkedin_auth_test.log for details")
    logger.info("=" * 60)
