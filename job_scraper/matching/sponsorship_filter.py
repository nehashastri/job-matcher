"""
LLM-backed sponsorship eligibility filter.

Checks whether a role offers visa sponsorship using an LLM and rule-based heuristics.
Integrates with OpenAI and config for eligibility decisions.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

from config.config import Config, get_config
from config.logging_utils import get_logger
from openai import OpenAI


class SponsorshipFilter:
    """
    Check whether a role offers visa sponsorship using an LLM.
    Attributes:
        config (Config): Configuration instance
        logger: Logger instance
        client: OpenAI client for LLM queries
    """

    def __init__(
        self,
        openai_client: Any | None = None,
        config: Config | None = None,
        logger=None,
    ):
        """
        Initialize SponsorshipFilter.
        Args:
            openai_client (Any | None): OpenAI client for LLM queries
            config (Config | None): Configuration instance
            logger: Logger instance
        """
        logger = logger or get_logger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        self.config = config or get_config()
        self.logger = logger or get_logger(__name__)
        self.client: Any | None = openai_client or self._maybe_create_client()

    def check(
        self, job_description: str, requires_sponsorship: bool | None = None
    ) -> dict[str, Any]:
        """
        Return sponsorship/eligibility decision as {"accepts_sponsorship": bool, "reason": str}.
        Args:
            job_description (str): Job description text
            requires_sponsorship (bool | None): If True, check for sponsorship
        Returns:
            dict[str, Any]: Decision and reason
        """
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.check")
        needs_sponsorship = requires_sponsorship
        if needs_sponsorship is None:
            needs_sponsorship = getattr(self.config, "requires_sponsorship", True)

        if not needs_sponsorship:
            self.logger.info(
                "Sponsorship check skipped (requires_sponsorship disabled); accepting job"
            )
            return {
                "accepts_sponsorship": True,
                "reason": "requires_sponsorship disabled",
            }

        if not job_description:
            self.logger.warning(
                "No job description provided; assuming sponsorship accepted"
            )
            return {"accepts_sponsorship": True, "reason": "No description provided"}

        lowered = job_description.lower()

        unpaid_reason = self._check_unpaid_or_volunteer(lowered)
        if unpaid_reason:
            self.logger.info(f"Eligibility check: REJECTED ({unpaid_reason})")
            return {"accepts_sponsorship": False, "reason": unpaid_reason}

        exp_reason = self._check_experience_requirement(lowered)
        if exp_reason:
            self.logger.info(f"Eligibility check: REJECTED ({exp_reason})")
            return {"accepts_sponsorship": False, "reason": exp_reason}

        phd_reason = self._check_phd_requirement(lowered)
        if phd_reason:
            self.logger.info(f"Eligibility check: REJECTED ({phd_reason})")
            return {"accepts_sponsorship": False, "reason": phd_reason}

        strong_negative = self._find_strong_negative_phrase(lowered)
        if strong_negative:
            self.logger.info(
                f"Sponsorship check: HEURISTIC REJECT (strong negative phrase: {strong_negative})"
            )
            return {
                "accepts_sponsorship": False,
                "reason": f"Found strong negative: {strong_negative}",
            }

        if not self._has_sponsorship_signal(lowered):
            self.logger.info(
                "No sponsorship-related language found; assuming sponsorship is accepted"
            )
            return {
                "accepts_sponsorship": True,
                "reason": "No sponsorship info present; assumed accept",
            }

        # Always use single-turn prompt and GPT-5-nano for sponsorship check
        try:
            with open("data/sponsorship_prompt.txt", "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        except Exception:
            prompt = (
                "You are evaluating sponsorship for a candidate on F-1 STEM OPT who will need "
                "continued work authorization (e.g., H-1B or similar). From the job description, "
                'decide if the employer supports work visas. Return JSON only: {"accepts_sponsorship": '
                'true|false, "reason": "brief explanation"}. Reject ONLY when the description explicitly '
                "denies sponsorship or requires unrestricted work authorization. Treat any of these as NOT sponsoring: "
                "no visa sponsorship, cannot hire international candidates, US citizens only, must have "
                "permanent work authorization/GC/USC, no OPT/CPT, must already be authorized without "
                "sponsorship. If the description is unclear or does not mention sponsorship, return "
                "accepts_sponsorship=true (default accept). If the description is positive about sponsorship "
                "(e.g., we sponsor H-1B/TN/O-1) or is open to international/OPT, return accepts_sponsorship=true."
            )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": job_description},
        ]

        self.logger.info("Sponsorship check: consulting LLM (single-turn, GPT-5-nano)")

        result = {"accepts_sponsorship": True, "reason": "LLM unavailable"}

        if not self.client:
            self.logger.warning(
                "OpenAI client not configured; assuming sponsorship is accepted for this role"
            )
            return result

        try:
            # Explicitly use GPT-5-nano for sponsorship check
            data = self._call_llm(messages, model="gpt-5-nano")
            accepts = bool(data.get("accepts_sponsorship", True))
            reason = data.get("reason", "No reason provided")
            result = {"accepts_sponsorship": accepts, "reason": reason}
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.error(
                f"Sponsorship check failed; defaulting to accept. Error: {exc}"
            )
            result = {
                "accepts_sponsorship": True,
                "reason": f"LLM error (assumed accept): {exc}",
            }

        # If the LLM rejected merely due to lack of explicit mention, default to accept unless a strong negative exists.
        if not result["accepts_sponsorship"]:
            lowered_reason = str(result.get("reason", "")).lower()
            no_info_markers = [
                "does not mention",
                "no mention",
                "not mention",
                "unspecified",
                "unclear",
                "not specified",
                "no information",
                "not provided",
                "unknown",
            ]
            if any(marker in lowered_reason for marker in no_info_markers):
                result = {
                    "accepts_sponsorship": True,
                    "reason": "LLM uncertain (no explicit denial); defaulting to accept",
                }

        if result["accepts_sponsorship"]:
            self.logger.info(
                f"Sponsorship check: ACCEPTED (sponsors visas). Reason: {self._short_reason(result['reason'])}"
            )
        else:
            self.logger.info(
                f"Sponsorship check: REJECTED (no sponsorship). Reason: {self._short_reason(result['reason'])}"
            )

        return result

    # ------------------------------------------------------------------
    # Eligibility helpers
    # ------------------------------------------------------------------
    def _check_unpaid_or_volunteer(self, lowered_text: str) -> str | None:
        if getattr(self.config, "reject_unpaid_roles", True):
            self.logger.info(
                f"[ENTER] {__file__}::{self.__class__.__name__}._check_unpaid_or_volunteer"
            )
            unpaid_keywords = [
                "unpaid",
                "no pay",
                "without pay",
                "no compensation",
                "uncompensated",
                "stipend only",
            ]
            if any(k in lowered_text for k in unpaid_keywords):
                return "Unpaid role detected"

        if getattr(self.config, "reject_volunteer_roles", True):
            volunteer_keywords = [
                "volunteer",
                "voluntary position",
                "voluntary role",
            ]
            if any(k in lowered_text for k in volunteer_keywords):
                return "Volunteer role detected"

        return None

    def _check_experience_requirement(self, lowered_text: str) -> str | None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._check_experience_requirement"
        )
        min_years = getattr(self.config, "min_required_experience_years", 0)
        if min_years <= 0:
            return None

        import re

        pattern = re.compile(
            r"(\d+)\s*\+?\s*(?:years|year|yrs|yr)[^\n]{0,20}experience"
        )
        for match in pattern.finditer(lowered_text):
            years = int(match.group(1))
            if years > min_years:
                return f"Experience requirement too high ({years}+ years > allowed {min_years})"
        return None

    def _check_phd_requirement(self, lowered_text: str) -> str | None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._check_phd_requirement"
        )
        allow_phd = getattr(self.config, "allow_phd_required", True)
        if allow_phd:
            return None

        phd_keywords = ["phd", "ph.d", "doctorate", "doctoral"]
        if any(k in lowered_text for k in phd_keywords):
            return "PhD requirement detected"
        return None

    @staticmethod
    def _has_sponsorship_signal(lowered_text: str) -> bool:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::SponsorshipFilter._has_sponsorship_signal")
        """Heuristic to detect if the description mentions sponsorship/authorization."""

        keywords = [
            "visa",
            "sponsor",
            "sponsorship",
            "work authorization",
            "international",
            "authorisation",
            "h-1b",
            "h1b",
            "tn visa",
            "o-1",
            "o1",
            "green card",
            "gc holder",
            "permanent resident",
            "citizen",
            "citizens only",
            "usc",
            "c2c",
            "w2",
            "e-verify",
            "opt",
            "stem opt",
            "cpt",
            "work permit",
            "permanent work authorization",
            "must be eligible to work",
            "authorized to work",
            "authorization to work",
            "non-citizen",
            "relocation/visa",
        ]
        return any(keyword in lowered_text for keyword in keywords)

    @staticmethod
    def _find_strong_negative_phrase(lowered_text: str) -> str | None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"[ENTER] {__file__}::SponsorshipFilter._find_strong_negative_phrase"
        )
        """Detect phrases that clearly deny sponsorship to short-circuit LLM calls."""

        strong_negatives = [
            "no visa sponsorship",
            "without sponsorship",
            "cannot sponsor",
            "will not sponsor",
            "not able to sponsor",
            "cannot hire international",
            "international candidates will not be considered",
            "us citizens only",
            "citizens only",
            "must be a us citizen",
            "usc only",
            "permanent resident only",
            "green card holders only",
            "must have permanent work authorization",
            "must have unrestricted work authorization",
            "no opt",
            "no cpt",
            "no h-1b",
            "no h1b",
            "no visa transfer",
            "no relocation or visa",
            "no relocation/visa",
            "must be authorized to work without sponsorship",
        ]

        for phrase in strong_negatives:
            if phrase in lowered_text:
                return phrase
        return None

    def _maybe_create_client(self) -> OpenAI | None:
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._maybe_create_client"
        )
        """Create an OpenAI client when an API key is present."""

        api_key = getattr(self.config, "openai_api_key", "")
        if not api_key:
            return None
        try:
            return OpenAI(api_key=api_key)
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.warning(f"Failed to initialize OpenAI client: {exc}")
            return None

    def _call_llm(
        self, messages: list[dict[str, str]], model: str = "gpt-3.5-turbo"
    ) -> dict[str, Any]:
        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._call_llm")
        """Call OpenAI using chat.completions or responses for JSON output."""

        if self.client is None:
            raise RuntimeError("OpenAI client not initialized")

        client = cast(Any, self.client)
        typed_messages = cast(list[Any], messages)

        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            kwargs = dict(
                model=model,
                messages=typed_messages,
                response_format={"type": "json_object"},
            )
            if (
                model.startswith("gpt-5")
                or model.startswith("gpt-4.1")
                or model.startswith("gpt-4-turbo")
            ):
                kwargs["max_completion_tokens"] = 512
            else:
                kwargs["max_tokens"] = 512
                kwargs["temperature"] = 0
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content if resp.choices else "{}"
            return json.loads(content or "{}")

        if hasattr(client, "responses"):
            kwargs = dict(
                model=model,
                messages=typed_messages,
                response_format={"type": "json_object"},
            )
            if not (
                model.startswith("gpt-5")
                or model.startswith("gpt-4.1")
                or model.startswith("gpt-4-turbo")
            ):
                kwargs["temperature"] = "0"
            response = client.responses.create(**kwargs)

            content = ""
            output = getattr(response, "output", None)
            if output and len(output) > 0:
                first_output = output[0]
                inner_content = getattr(first_output, "content", None)
                if inner_content and len(inner_content) > 0:
                    text_candidate = getattr(inner_content[0], "text", "")
                    content = (
                        text_candidate
                        if isinstance(text_candidate, str)
                        else str(text_candidate)
                    )
            elif hasattr(response, "content"):
                content = getattr(response, "content")
            return json.loads(content or "{}")

        # Always return a dict on all code paths
        return {}

    @staticmethod
    def _short_reason(reason: str) -> str:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::SponsorshipFilter._short_reason")
        """Return up to two sentences for concise logging."""

        if not reason:
            return "No reason provided"

        sentences = re.split(r"(?<=[.!?])\s+", reason.strip())
        joined = " ".join(sentences[:2]).strip()
        return joined or reason.strip()[:240]
