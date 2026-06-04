"""
Company blocklist storage implementation.
Handles reading and writing to company_blocklist.json.
"""

import json
import logging
from pathlib import Path
from typing import Any

from config.config import DATA_DIR

logger = logging.getLogger(__name__)


class BlocklistStore:
    """
    Store and manage company blocklist in a JSON file.

    Attributes:
        data_dir (Path): Directory where blocklist JSON is stored.
        blocklist_file (Path): Path to company_blocklist.json file.
    """

    def __init__(self, data_dir: str | Path | None = None):
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        """
        Initialize BlocklistStore.

        Args:
            data_dir (str | Path | None): Directory to store blocklist file. Defaults to DATA_DIR.
        """
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(exist_ok=True)
        self.blocklist_file = self.data_dir / "company_blocklist.json"
        # Initialize with default structure if file doesn't exist
        if not self.blocklist_file.exists():
            self._init_blocklist()

    def _init_blocklist(self):
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._init_blocklist")
        """
        Initialize blocklist file with default structure if not present.
        """
        default_blocklist = {
            "blocklist": [],
            "patterns": [],
            "notes": "This list contains known HR/staffing firms and recruiting companies. Additional companies may be added automatically via LLM detection.",
        }
        self._write_blocklist(default_blocklist)
        logger.info("Initialized empty company blocklist")

    def _read_blocklist(self) -> dict[str, Any]:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._read_blocklist")
        """
        Read blocklist data from JSON file.

        Returns:
            dict[str, Any]: Blocklist data dictionary.
        """
        try:
            with open(self.blocklist_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading blocklist: {str(e)}")
            return {"blocklist": [], "patterns": [], "notes": ""}

    def _write_blocklist(self, data: dict[str, Any]):
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._write_blocklist")
        """
        Write blocklist data to JSON file.

        Args:
            data (dict[str, Any]): Blocklist data to write.
        """
        try:
            with open(self.blocklist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing blocklist: {str(e)}")

    def add(self, company: str) -> bool:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.add")
        """
        Add a company to the blocklist if not already present.

        Args:
            company (str): Company name to add.

        Returns:
            bool: True if added, False if already present or error.
        """
        try:
            data = self._read_blocklist()
            blocklist = data.get("blocklist", [])

            if company in blocklist:
                logger.debug(f"Company '{company}' already in blocklist")
                return False

            blocklist.append(company)
            data["blocklist"] = blocklist
            self._write_blocklist(data)
            logger.info(f"Added '{company}' to blocklist")
            return True

        except Exception as e:
            logger.error(f"Error adding company to blocklist: {str(e)}")
            return False

    def remove(self, company: str) -> bool:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.remove")
        """
        Remove a company from the blocklist.

        Args:
            company (str): Company name to remove.

        Returns:
            bool: True if removed, False if not present or error.
        """
        try:
            data = self._read_blocklist()
            blocklist = data.get("blocklist", [])

            if company not in blocklist:
                logger.debug(f"Company '{company}' not in blocklist")
                return False

            blocklist.remove(company)
            data["blocklist"] = blocklist
            self._write_blocklist(data)
            logger.info(f"Removed '{company}' from blocklist")
            return True

        except Exception as e:
            logger.error(f"Error removing company from blocklist: {str(e)}")
            return False

    def get_all_companies(self) -> list[str]:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.get_all_companies")
        """
        Get all companies in the blocklist.

        Returns:
            list[str]: List of company names.
        """
        data = self._read_blocklist()
        return data.get("blocklist", [])

    def get_all_patterns(self) -> list[str]:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.get_all_patterns")
        """
        Get all regex patterns in the blocklist.

        Returns:
            list[str]: List of regex patterns.
        """
        data = self._read_blocklist()
        return data.get("patterns", [])

    def is_blocked(self, company: str) -> bool:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.is_blocked")
        """
        Check if a company is in the blocklist.

        Args:
            company (str): Company name to check.

        Returns:
            bool: True if blocked, False otherwise.
        """
        companies = self.get_all_companies()
        return company in companies

    def add_pattern(self, pattern: str) -> bool:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.add_pattern")
        """
        Add a regex pattern to the blocklist if not already present.

        Args:
            pattern (str): Regex pattern to add.

        Returns:
            bool: True if added, False if already present or error.
        """
        try:
            data = self._read_blocklist()
            patterns = data.get("patterns", [])

            if pattern in patterns:
                logger.debug(f"Pattern '{pattern}' already in blocklist")
                return False

            patterns.append(pattern)
            data["patterns"] = patterns
            self._write_blocklist(data)
            logger.info(f"Added pattern '{pattern}' to blocklist")
            return True

        except Exception as e:
            logger.error(f"Error adding pattern to blocklist: {str(e)}")
            return False

    def get_stats(self) -> dict[str, int]:
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.get_stats")
        """
        Get statistics about the blocklist (number of companies and patterns).

        Returns:
            dict[str, int]: Dictionary with counts for companies and patterns.
        """
        data = self._read_blocklist()
        return {
            "companies": len(data.get("blocklist", [])),
            "patterns": len(data.get("patterns", [])),
        }
