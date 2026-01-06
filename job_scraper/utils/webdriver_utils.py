import time


def safe_get(driver, logger, url, retries=2, delay=2.0):
    """Navigate to a URL with lightweight retries to reduce flakiness in headless runs."""
    if driver is None:
        return False
    for attempt in range(retries):
        try:
            driver.get(url)
            return True
        except Exception as exc:
            logger.debug(f"Nav attempt {attempt + 1}/{retries} failed for {url}: {exc}")
            time.sleep(delay)
    return False
