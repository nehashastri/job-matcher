"""
Company blocklist matching and persistence.

Implements exact and pattern-based company filtering with lightweight
JSON-backed persistence. Blocklist entries are case-insensitive and
support simple wildcards ("*") or raw regular expressions.

Features:
- Exact and pattern-based company filtering
- JSON-backed persistence for blocklist
- Case-insensitive matching
- Wildcard and regex support
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from config.config import Config, get_config
from config.logging_utils import get_logger


class Blocklist:
    """
    Company blocklist with exact/regex matching and persistence.
    Attributes:
        config (Config): Configuration instance
        logger: Logger instance
        file_path (Path): Path to blocklist JSON file
        blocked (list[str]): List of exact blocked company names
        patterns (list[str]): List of pattern/regex blocked companies
    """

    def is_blocked(self, company: str) -> bool:
        """
        Check if a company is blocked (exact or pattern match).
        Args:
            company (str): Company name to check
        Returns:
            bool: True if blocked, False otherwise
        """
        if not company:
            return False
        name = company.strip()
        if not name:
            return False
        if self._matches_exact(name):
            self.logger.info(f"Rejected company via blocklist (exact match): {name}")
            return True
        if self._matches_pattern(name):
            self.logger.info(f"Rejected company via blocklist (pattern match): {name}")
            return True
        return False

    def __init__(
        self,
        file_path: str | Path | None = None,
        config: Config | None = None,
        logger=None,
    ):
        self.logger = logger or get_logger(__name__)
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        """
        Initialize Blocklist instance and load blocklist from disk.
        Args:
            file_path (str | Path | None): Path to blocklist file
            config (Config | None): Configuration instance
            logger: Logger instance
        """
        self.config = config or get_config()
        self.file_path = (
            Path(file_path) if file_path else Path(self.config.blocklist_path)
        )
        self.blocked: list[str] = []
        self.patterns: list[str] = []
        self._load()

    def add(self, company: str) -> bool:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.add")
        """
        Add a company to the blocklist and persist it to disk.
        Args:
            company (str): Company name to add
        Returns:
            bool: True if added, False otherwise

        Returns True when a new company was added.
        """

        name = company.strip() if company else ""
        if not name:
            return False

        if self.is_blocked(name):
            return False

        self.blocked.append(name)
        self.blocked = sorted(set(self.blocked), key=str.lower)
        self._persist()

        # Keep config in sync for callers that reuse the shared instance
        if hasattr(self.config, "blocklist"):
            self.config.blocklist = self.blocked

        self.logger.info(f"Added company to blocklist: {name}")
        return True

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _load(self) -> None:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._load")
        """Load blocklist entries and patterns from JSON file."""

        try:
            if self.file_path.exists():
                with open(self.file_path, encoding="utf-8") as f:
                    data = json.load(f)
                self.blocked = list(self._clean_list(data.get("blocklist", [])))
                self.patterns = list(self._clean_list(data.get("patterns", [])))
            else:
                # Fall back to config-loaded values if file is missing
                self.blocked = list(
                    self._clean_list(getattr(self.config, "blocklist", []))
                )
                self.patterns = list(
                    self._clean_list(getattr(self.config, "blocklist_patterns", []))
                )
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.warning(
                f"Failed to load blocklist from {self.file_path}: {exc}"
            )
            self.blocked, self.patterns = [], []

    def _persist(self) -> None:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._persist")
        """Persist blocklist data to JSON, preserving existing patterns/notes."""

        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            data = {"blocklist": list(self.blocked), "patterns": list(self.patterns)}

            # Preserve existing metadata such as "notes"
            if self.file_path.exists():
                with open(self.file_path, encoding="utf-8") as f:
                    existing = json.load(f)
                for key, value in existing.items():
                    if key not in data:
                        data[key] = value

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.warning(
                f"Failed to persist blocklist to {self.file_path}: {exc}"
            )

    def _matches_exact(self, company: str) -> bool:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._matches_exact"
        )
        return any(company.lower() == item.lower() for item in self.blocked)

    def _matches_pattern(self, company: str) -> bool:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._matches_pattern"
        )
        for pattern in self.patterns:
            regex = self._to_regex(pattern)
            try:
                if re.search(regex, company, flags=re.IGNORECASE):
                    return True
            except re.error:
                # Ignore malformed patterns; keep scanning
                self.logger.debug(f"Ignoring invalid blocklist pattern: {pattern}")
                continue
        return False

    @staticmethod
    def _to_regex(pattern: str) -> str:
        import logging

        logging.getLogger(__name__).info(f"[ENTER] {__file__}::Blocklist._to_regex")
        """Convert simple wildcard patterns to regex. Existing regex still works."""

        # Replace shell-style wildcard with regex equivalent
        return pattern.replace("*", ".*")

    @staticmethod
    def _clean_list(values: Iterable[str]) -> Iterable[str]:
        import logging

        logging.getLogger(__name__).info(f"[ENTER] {__file__}::Blocklist._clean_list")
        return [v for v in values if isinstance(v, str) and v.strip()]
