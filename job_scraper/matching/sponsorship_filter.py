"""LLM-backed sponsorship eligibility filter."""

from __future__ import annotations

import json
from typing import Any

from config.config import Config, get_config
from config.logging_utils import get_logger
from openai import OpenAI


class SponsorshipFilter:
    """Check whether a role offers visa sponsorship using an LLM."""

    def __init__(
        self,
        openai_client: Any | None = None,
        config: Config | None = None,
        logger=None,
    ):
        self.config = config or get_config()
        self.logger = logger or get_logger(__name__)
        self.client = openai_client or self._maybe_create_client()

    def check(
        self, job_description: str, requires_sponsorship: bool | None = None
    ) -> dict[str, Any]:
        """Return sponsorship decision as {"accepts_sponsorship": bool, "reason": str}."""

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

        prompt = (
            "You are evaluating sponsorship for a candidate on F-1 STEM OPT who will need "
            "continued work authorization (e.g., H-1B or similar). From the job description, "
            'decide if the employer supports work visas. Return JSON only: {"accepts_sponsorship": '
            'true|false, "reason": "brief explanation"}. Treat any of these as NOT sponsoring: '
            "no visa sponsorship, cannot hire international candidates, US citizens only, must have "
            "permanent work authorization/GC/USC, no OPT/CPT, must already be authorized without "
            "sponsorship. If the description is positive about sponsorship (e.g., we sponsor H-1B/TN/O-1) "
            "or is open to international/OPT, return accepts_sponsorship=true."
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": job_description[:4000]},
        ]

        self.logger.info(
            "Sponsorship check: consulting LLM (sponsorship signals detected, no strong negatives)"
        )

        result = {"accepts_sponsorship": True, "reason": "LLM unavailable"}

        if not self.client:
            self.logger.warning(
                "OpenAI client not configured; assuming sponsorship is accepted for this role"
            )
            return result

        try:
            data = self._call_llm(messages)
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

        if result["accepts_sponsorship"]:
            self.logger.info(
                f"Sponsorship check: ACCEPTED (sponsors visas). Reason: {result['reason']}"
            )
        else:
            self.logger.info(
                f"Sponsorship check: REJECTED (no sponsorship). Reason: {result['reason']}"
            )

        return result

    @staticmethod
    def _has_sponsorship_signal(lowered_text: str) -> bool:
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
        """Create an OpenAI client when an API key is present."""

        api_key = getattr(self.config, "openai_api_key", "")
        if not api_key:
            return None
        try:
            return OpenAI(api_key=api_key)
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.warning(f"Failed to initialize OpenAI client: {exc}")
            return None

    def _call_llm(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call OpenAI using chat.completions or responses for JSON output."""

        model = self.config.openai_model or "gpt-4o-mini"

        if hasattr(self.client, "chat") and hasattr(self.client.chat, "completions"):
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content if resp.choices else "{}"
            return json.loads(content or "{}")

        if hasattr(self.client, "responses"):
            response = self.client.responses.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )

            content = ""
            if getattr(response, "output", None):
                content = response.output[0].content[0].text  # type: ignore[index]
            elif hasattr(response, "content"):
                content = getattr(response, "content")
            return json.loads(content or "{}")

        raise RuntimeError("OpenAI client missing chat.completions or responses API")
