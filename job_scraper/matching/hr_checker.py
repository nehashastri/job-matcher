from __future__ import annotations

import json
from typing import Any

from config.config import Config, get_config
from config.logging_utils import get_logger
from filtering.blocklist import Blocklist
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from utils.model_utils import short_reason

"""LLM-backed HR/staffing company detection."""


class HRChecker:
    """Detect HR/staffing companies via LLM and auto-blocklist."""

    def __init__(
        self,
        openai_client: Any | None = None,
        config: Config | None = None,
        blocklist: Blocklist | None = None,
        logger=None,
    ):
        self.config = config or get_config()
        self.logger = logger or get_logger(__name__)
        self.blocklist = blocklist or Blocklist(config=self.config, logger=self.logger)
        self.client = openai_client or self._maybe_create_client()

    def check(
        self,
        company: str,
        description: str = "",
        accept_hr_companies: bool | None = None,
    ) -> dict[str, Any]:
        """Check if company is an HR/staffing firm.

        Returns a dict: {"is_hr_company": bool, "reason": str}
        If the company is detected as HR (or on error), it is auto-added to the blocklist.
        """

        if not company:
            return {"is_hr_company": False, "reason": "No company provided"}

        company_name = company.strip()

        # Determine whether to skip HR filtering (inverse of reject flag)
        skip_hr_filter = accept_hr_companies
        if skip_hr_filter is None:
            skip_hr_filter = not getattr(self.config, "reject_hr_companies", True)

        if skip_hr_filter:
            self.logger.info(
                f"HR check skipped for {company_name} (accept_hr_companies enabled); treating as accepted"
            )
            return {"is_hr_company": False, "reason": "accept_hr_companies enabled"}

        # If already blocked, no need to ask the LLM
        if self.blocklist.is_blocked(company_name):
            self.logger.info(
                f"Rejected {company_name} as HR/staffing (already in blocklist); downstream halted"
            )
            return {"is_hr_company": True, "reason": "Company already on blocklist"}

        # Build LLM request
        try:
            with open("data/LLM_hr_check.txt", "r", encoding="utf-8") as f:
                prompt_template = f.read().strip()
        except Exception:
            prompt_template = (
                'Determine if the company "{company_name}" is a staffing, recruitment, HR, or temp '
                'agency firm. Return JSON: {{"is_hr_company": true/false, "reason": "brief explanation"}}.'
            )
        prompt = prompt_template.format(company_name=company_name)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Company: {company_name}\nContext: {description[:4000] if description else 'No additional context provided.'}",
            },
        ]

        # Default to accept; only mark HR when LLM explicitly flags it
        result = {"is_hr_company": False, "reason": "LLM unavailable"}

        if not self.client:
            self.logger.warning(
                f"OpenAI client not configured; accepting {company_name} (HR check skipped)"
            )
        else:
            try:
                data = self._call_llm(messages)
                is_hr = bool(data.get("is_hr_company", False))
                reason = data.get("reason", "No reason provided")
                result = {"is_hr_company": is_hr, "reason": reason}
            except (
                Exception
            ) as exc:  # pragma: no cover - exercised via invalid JSON test
                # Invalid JSON or API error → assume accept per requirement
                self.logger.error(
                    f"HR check failed for {company_name}; defaulting to accept. Error: {exc}"
                )
                result = {
                    "is_hr_company": False,
                    "reason": f"LLM error (assumed accept): {exc}",
                }

        if result["is_hr_company"]:
            added = self.blocklist.add(company_name)
            if added:
                self.logger.info(
                    f"Rejected {company_name} as HR/staffing; added to blocklist. Reason: {short_reason(result['reason'])}"
                )
            else:
                self.logger.info(
                    f"Rejected {company_name} as HR/staffing (already blocked). Reason: {short_reason(result['reason'])}"
                )
        else:
            self.logger.info(
                f"Accepted {company_name}; HR check clear. Reason: {short_reason(result['reason'])}"
            )

        return result

    def _maybe_create_client(self) -> OpenAI | None:
        """Create an OpenAI client if an API key is present."""

        api_key = getattr(self.config, "openai_api_key", "")
        if not api_key:
            return None
        try:
            return OpenAI(api_key=api_key)
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.warning(f"Failed to initialize OpenAI client: {exc}")
            return None

    def _call_llm(self, messages: list[ChatCompletionMessageParam]) -> dict[str, Any]:
        """Call OpenAI using chat.completions API only."""
        model = self.config.openai_model or "gpt-3.5-turbo"
        if (
            not self.client
            or not hasattr(self.client, "chat")
            or not hasattr(self.client.chat, "completions")
        ):
            raise RuntimeError("OpenAI client missing chat.completions API")
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content if resp.choices else "{}"
            return json.loads(content or "{}")
        except Exception as exc:
            self.logger.error(f"OpenAI API call failed: {exc}")
            return {}
