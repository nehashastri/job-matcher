"""Compatibility exports for legacy scrapers package."""

from scraping.base_scraper import BaseScraper
from scraping.linkedin_scraper import LinkedInScraper

__all__ = [
    "BaseScraper",
    "LinkedInScraper",
]
