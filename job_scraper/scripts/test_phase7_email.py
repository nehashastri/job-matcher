"""
Manual test script for Phase 7: Email Notifications
Tests email sending with real Gmail SMTP connection
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import Config
from config.logging_utils import setup_logging
from notifications.email_notifier import EmailNotifier

# Setup logging
logger = setup_logging()


def test_email_configuration():
    """Test email configuration validation"""
    logger.info("=" * 60)
    logger.info("Testing Email Configuration")
    logger.info("=" * 60)

    config = Config()
    notifier = EmailNotifier(config)

    logger.info(f"Email notifications enabled: {notifier.enabled}")
    logger.info(f"SMTP server: {notifier.smtp_server}")
    logger.info(f"SMTP port: {notifier.smtp_port}")
    logger.info(f"SMTP username: {notifier.smtp_username}")
    logger.info(f"Email from: {notifier.email_from}")
    logger.info(f"Email to: {notifier.email_to}")

    if notifier._validate_config():
        logger.info("✅ Email configuration is valid")
        return True
    else:
        logger.error("❌ Email configuration is invalid")
        return False


def test_smtp_connection():
    """Test SMTP connection"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing SMTP Connection")
    logger.info("=" * 60)

    config = Config()
    notifier = EmailNotifier(config)

    if notifier.test_connection():
        logger.info("✅ SMTP connection test successful")
        return True
    else:
        logger.error("❌ SMTP connection test failed")
        return False


def test_send_sample_email():
    """Send a sample email notification"""
    logger.info("\n" + "=" * 60)
    logger.info("Sending Sample Email Notification")
    logger.info("=" * 60)

    config = Config()
    notifier = EmailNotifier(config)

    # Sample job data
    sample_job = {
        "title": "Senior Software Engineer",
        "company": "Acme Corporation",
        "location": "San Francisco, CA (Remote)",
        "match_score": 9,
        "job_url": "https://www.linkedin.com/jobs/view/12345678",
        "applicants": "42 applicants",
        "posted_date": "2 days ago",
        "seniority": "Mid-Senior level",
        "remote": "Remote",
    }

    connection_count = 5

    logger.info("Sample job details:")
    logger.info(f"  Title: {sample_job['title']}")
    logger.info(f"  Company: {sample_job['company']}")
    logger.info(f"  Location: {sample_job['location']}")
    logger.info(f"  Match Score: {sample_job['match_score']}/10")
    logger.info(f"  Connection Requests: {connection_count}")

    if notifier.send_job_notification(sample_job, connection_count):
        logger.info("✅ Sample email sent successfully")
        logger.info(f"Check your inbox at {notifier.email_to}")
        return True
    else:
        logger.error("❌ Failed to send sample email")
        return False


def test_disabled_notifications():
    """Test behavior when notifications are disabled"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Disabled Notifications")
    logger.info("=" * 60)

    config = Config()
    config.enable_email_notifications = False
    notifier = EmailNotifier(config)

    sample_job = {
        "title": "Test Job",
        "company": "Test Company",
        "location": "Remote",
        "match_score": 8,
        "job_url": "https://example.com",
    }

    result = notifier.send_job_notification(sample_job, connection_count=0)

    if not result:
        logger.info("✅ Correctly skipped sending when notifications disabled")
        return True
    else:
        logger.error("❌ Should not send email when notifications disabled")
        return False


def main():
    """Run all manual tests"""
    logger.info("Starting Phase 7 Email Notification Tests")
    logger.info("=" * 60)

    results = []

    # Test 1: Configuration validation
    try:
        results.append(("Configuration Validation", test_email_configuration()))
    except Exception as e:
        logger.error(f"❌ Configuration test failed with error: {e}")
        results.append(("Configuration Validation", False))

    # Test 2: SMTP connection (only if config is valid)
    if results[0][1]:
        try:
            results.append(("SMTP Connection", test_smtp_connection()))
        except Exception as e:
            logger.error(f"❌ SMTP connection test failed with error: {e}")
            results.append(("SMTP Connection", False))
    else:
        logger.info("Skipping SMTP connection test due to invalid configuration")
        results.append(("SMTP Connection", False))

    # Test 3: Send sample email (only if connection works)
    if results[1][1]:
        try:
            results.append(("Send Sample Email", test_send_sample_email()))
        except Exception as e:
            logger.error(f"❌ Send email test failed with error: {e}")
            results.append(("Send Sample Email", False))
    else:
        logger.info("Skipping email send test due to connection failure")
        results.append(("Send Sample Email", False))

    # Test 4: Disabled notifications
    try:
        results.append(("Disabled Notifications", test_disabled_notifications()))
    except Exception as e:
        logger.error(f"❌ Disabled notifications test failed with error: {e}")
        results.append(("Disabled Notifications", False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    logger.info(f"\nPassed: {passed_count}/{total_count}")

    if passed_count == total_count:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
