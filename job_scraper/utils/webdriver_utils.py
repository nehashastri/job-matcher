import time


def safe_get(driver, logger, url, retries=2, delay=2.0):
    """Navigate to a URL with lightweight retries to reduce flakiness in headless runs."""
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
