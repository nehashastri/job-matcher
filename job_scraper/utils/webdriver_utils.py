# Standard library for time delays
import time


def safe_get(driver, logger, url, retries=2, delay=2.0):
    logger.info(f"[ENTER] {__file__}::safe_get")
    """
    Attempt to navigate a Selenium WebDriver to a given URL, with retry logic.

    Args:
        driver: Selenium WebDriver instance used for navigation.
        logger: Logger object for logging navigation attempts and errors.
        url: The target URL to navigate to.
        retries: Number of retry attempts if navigation fails (default: 2).
        delay: Delay in seconds between retries (default: 2.0).

    Returns:
        True if navigation succeeds, False otherwise.
    """
    logger.info(f"Attempting to navigate to {url} with {retries} retries.")
    if driver is None:
        logger.error("WebDriver is None; cannot navigate.")
        return False
    for attempt in range(retries):
        try:
            driver.get(url)
            logger.info(f"Navigation to {url} succeeded on attempt {attempt + 1}.")
            return True
        except Exception as exc:
            logger.warning(
                f"Nav attempt {attempt + 1}/{retries} failed for {url}: {exc}"
            )
            time.sleep(delay)
    logger.error(f"All navigation attempts failed for {url}.")
    return False
