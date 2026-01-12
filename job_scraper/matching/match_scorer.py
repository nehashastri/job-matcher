from __future__ import annotations

import json
from typing import Any, cast

from config.config import Config, get_config
from config.logging_utils import get_logger
from utils.model_utils import short_reason

"""
LLM-backed job/resume match scorer with optional rerank pass.

Scores job/resume matches using LLM, supports reranking with a second model.
Integrates with OpenAI, config, and logging utilities.
"""


class MatchScorer:
    """
    Scores job/resume matches using LLM, supports reranking with a second model.
    Attributes:
        config (Config): Configuration instance
        logger: Logger instance
        client: OpenAI client for LLM queries
    """

    def _build_messages(
        self,
        resume_text: str,
        job_details: dict,
        prompt: "str | None" = None,
    ) -> list[dict[str, str]]:
        """
        Build messages for LLM prompt for job/resume matching.
        Args:
            resume_text (str): Resume text
            job_details (dict): Job details
            prompt (str | None): Optional prompt override
        Returns:
            list[dict[str, str]]: Messages for LLM chat completion
        """
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._build_messages"
        )
        description = job_details.get("description", "")
        if prompt is None:
            prompt = (
                "You are a concise matcher. Score 0-10 (float) how well the candidate fits the job. "
                "Consider resume and preferences. If the job title or company is missing/blank, infer them "
                'from the description and return them. Return JSON only: {"score": number, "reason": string, '
                '"title": string, "company": string}. Keep title/company unchanged if already provided; otherwise, '
                "supply concise inferred values."
            )
        return [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Resume: {resume_text}\n"
                    f"Job Title: {job_details.get('title', '')}\n"
                    f"Company: {job_details.get('company', '')}\n"
                    f"Location: {job_details.get('location', '')}\n"
                    f"Description: {description[:4000]}"
                ),
            },
        ]

    def _maybe_create_client(self) -> Any:
        """
        Create OpenAI client if API key is available.
        Returns:
            Any: OpenAI client instance or None
        """
        self.logger.info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._maybe_create_client"
        )
        api_key = getattr(self.config, "openai_api_key", "")
        if not api_key:
            return None
        try:
            from openai import OpenAI

            return OpenAI(api_key=api_key)
        except Exception as exc:
            self.logger.warning(f"Failed to initialize OpenAI client: {exc}")
            return None

    @staticmethod
    def update_profiles_with_llm_results(
        profiles: list[dict], llm_results: dict
    ) -> list[dict]:
        """
        Overwrite company and title fields in profiles with values from LLM results.
        Expects llm_results to have 'matches', a list of dicts with 'name', 'title', 'company', 'profile_url'.
        Returns updated profiles list (matches only).
        Args:
            profiles (list[dict]): List of profile dicts
            llm_results (dict): LLM result dict with company/title
        Returns:
            list[dict]: Updated profiles
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[ENTER] {__file__}::MatchScorer.update_profiles_with_llm_results")
        updated = []
        for llm_profile in llm_results.get("matches", []):
            # Find matching profile by name and profile_url
            match = next(
                (
                    p
                    for p in profiles
                    if p.get("name") == llm_profile.get("name")
                    and p.get("profile_url") == llm_profile.get("profile_url")
                ),
                None,
            )
            if match:
                match["company"] = llm_profile.get("company", match.get("company", ""))
                match["title"] = llm_profile.get("title", match.get("title", ""))
                updated.append(match)
        return updated

    def __init__(
        self,
        config: "Config | None" = None,
        openai_client: Any = None,
        logger=None,
    ):
        logger = logger or get_logger(__name__)
        logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.__init__")
        self.config = config or get_config()
        self.logger = logger or get_logger(__name__)
        self.client = openai_client or self._maybe_create_client()

    def score(
        self,
        resume_text: str,
        job_details: dict,
        base_prompt: "str | None" = None,
        rerank_prompt: "str | None" = None,
    ) -> dict:
        """
        Score a job against resume/preferences.
        Returns dict with keys: score, reason, model_used, reranked (bool), reason_rerank, model_used_rerank.
        """

        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}.score")

        if not self.client:
            self.logger.warning(
                "OpenAI client not configured; defaulting match score to 0"
            )
            return {
                "score": 0.0,
                "reason": "LLM unavailable",
                "model_used": None,
                "reranked": False,
                "reason_rerank": None,
                "model_used_rerank": None,
            }

        # Load prompts from file if not provided
        if base_prompt is None:
            try:
                with open("data/LLM_base_score.txt", "r", encoding="utf-8") as f:
                    base_prompt = f.read().strip()
            except Exception:
                base_prompt = (
                    "You are a concise matcher. Score 0-10 (float) how well the candidate fits the job. "
                    "Consider resume and preferences. If the job title or company is missing/blank, infer them "
                    'from the description and return them. Return JSON only: {"score": number, "reason": string, '
                    '"title": string, "company": string}. Keep title/company unchanged if already provided; otherwise, '
                    "supply concise inferred values."
                )

        if rerank_prompt is None:
            try:
                with open("data/LLM_rerank_score.txt", "r", encoding="utf-8") as f:
                    rerank_prompt = f.read().strip()
            except Exception:
                rerank_prompt = base_prompt

        messages = self._build_messages(resume_text, job_details, prompt=base_prompt)
        base_model = self.config.openai_model or "gpt-4o-mini"
        rerank_model = self.config.openai_model_rerank or "gpt-4o"
        trigger = getattr(self.config, "job_match_rerank_trigger", 8)

        try:
            first_score, first_reason, inferred_title, inferred_company = (
                self._call_llm(messages, base_model)
            )
            inferred_title = inferred_title or job_details.get("title", "")
            inferred_company = inferred_company or job_details.get("company", "")
            short_first_reason = short_reason(first_reason)
            self.logger.info(
                f"LLM base score {first_score:.1f} ({base_model}): {short_first_reason}",
                extra={"llm_reason": short_first_reason},
            )
            reranked = False
            reason_rerank = None
            model_used_rerank = None

            needs_rerank = rerank_model != base_model and first_score >= trigger

            if needs_rerank:
                self.logger.info(
                    "Triggering rerank pass",
                    extra={
                        "base_model": base_model,
                        "rerank_model": rerank_model,
                        "first_score": first_score,
                        "trigger": trigger,
                        "llm_reason": short_first_reason,
                    },
                )
                reranked = True
                model_used_rerank = rerank_model
                rerank_messages = self._build_messages(
                    resume_text, job_details, prompt=rerank_prompt
                )
                rerank_score, reason_rerank, _, _ = self._call_llm(
                    rerank_messages, rerank_model
                )
                self.logger.info(
                    f"LLM rerank score {rerank_score:.1f} ({rerank_model}): {short_reason(reason_rerank)}",
                    extra={"llm_reason": short_reason(reason_rerank)},
                )
                return {
                    "score": rerank_score,
                    "reason": reason_rerank,
                    "model_used": rerank_model,
                    "reranked": reranked,
                    "reason_rerank": reason_rerank,
                    "model_used_rerank": model_used_rerank,
                    "first_score": first_score,
                    "reason_first": first_reason,
                    # Only base scoring returns title/company
                    "inferred_title": inferred_title,
                    "inferred_company": inferred_company,
                }

            return {
                "score": first_score,
                "reason": first_reason,
                "model_used": base_model,
                "reranked": reranked,
                "reason_rerank": reason_rerank,
                "model_used_rerank": model_used_rerank,
                "first_score": first_score,
                "reason_first": first_reason,
                "inferred_title": inferred_title,
                "inferred_company": inferred_company,
            }
        except Exception as exc:  # pragma: no cover - defensive
            threshold = getattr(self.config, "job_match_threshold", 8.0)
            fallback_score = min(10.0, max(threshold, 0.0) + 0.1)
            self.logger.error(
                f"Match scoring failed; defaulting to accept with score {fallback_score}: {exc}"
            )
            return {
                "score": fallback_score,
                "reason": f"LLM error (accepted): {exc}",
                "model_used": base_model,
                "reranked": False,
                "reason_rerank": None,
                "model_used_rerank": None,
                "first_score": fallback_score,
                "reason_first": f"LLM error (accepted): {exc}",
            }
            self.logger.warning(f"Failed to initialize OpenAI client: {exc}")
            return None

    def _call_llm(self, messages: list[dict[str, str]], model: str) -> tuple:
        """
        Call OpenAI using chat.completions or responses for JSON output.
        """

        self.logger.info(f"[ENTER] {__file__}::{self.__class__.__name__}._call_llm")

        if self.client is None:
            raise RuntimeError("OpenAI client not initialized")

        client = cast(Any, self.client)
        typed_messages = cast(list[Any], messages)

        # Prefer chat.completions
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            resp = client.chat.completions.create(
                model=model,
                messages=typed_messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content if resp.choices else "{}"
            data = json.loads(content or "{}")
            return (
                float(data.get("score", 0)),
                data.get("reason", ""),
                data.get("title", ""),
                data.get("company", ""),
            )

        # Fallback to responses API (matches mocks/tests style)
        if hasattr(client, "responses"):
            response = client.responses.create(
                model=model,
                messages=typed_messages,
                response_format={"type": "json_object"},
                temperature=0,
            )

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

            data = json.loads(content or "{}")
            return (
                float(data.get("score", 0)),
                data.get("reason", ""),
                data.get("title", ""),
                data.get("company", ""),
            )

        raise RuntimeError("OpenAI client missing chat.completions or responses API")
