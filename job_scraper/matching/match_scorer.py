"""LLM-backed job/resume match scorer with optional rerank pass."""

from __future__ import annotations

import json
from typing import Any, cast

from config.config import Config, get_config
from config.logging_utils import get_logger
from openai import OpenAI


class MatchScorer:
    def __init__(
        self,
        config: Config | None = None,
        openai_client: Any | None = None,
        logger=None,
    ):
        self.config = config or get_config()
        self.logger = logger or get_logger(__name__)
        self.client: Any | None = openai_client or self._maybe_create_client()

    def score(self, resume_text: str, preferences_text: str, job_details: dict) -> dict:
        """Score a job against resume/preferences.

        Returns dict with keys: score, reason, model_used, reranked (bool),
        reason_rerank, model_used_rerank.
        """

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

        messages = self._build_messages(resume_text, preferences_text, job_details)

        base_model = self.config.openai_model or "gpt-4o-mini"
        rerank_model = self.config.openai_model_rerank or base_model
        trigger = getattr(self.config, "job_match_rerank_trigger", 8)

        try:
            first_score, first_reason = self._call_llm(messages, base_model)
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
                    },
                )
                reranked = True
                model_used_rerank = rerank_model
                rerank_score, reason_rerank = self._call_llm(messages, rerank_model)
                return {
                    "score": rerank_score,
                    "reason": reason_rerank,
                    "model_used": rerank_model,
                    "reranked": reranked,
                    "reason_rerank": reason_rerank,
                    "model_used_rerank": model_used_rerank,
                }

            return {
                "score": first_score,
                "reason": first_reason,
                "model_used": base_model,
                "reranked": reranked,
                "reason_rerank": reason_rerank,
                "model_used_rerank": model_used_rerank,
            }
        except Exception as exc:  # pragma: no cover - defensive
            # Requirement: invalid/failed JSON → accept job and append
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
            }

    def _build_messages(
        self, resume_text: str, preferences_text: str, job_details: dict
    ) -> list[dict[str, str]]:
        description = job_details.get("description", "")
        prompt = (
            "You are a concise matcher. Score 0-10 (float) how well the candidate fits the job. "
            'Consider resume and preferences. Return JSON: {"score": number, "reason": string}.'
        )

        return [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Resume:\n{resume_text}\n\nPreferences:\n{preferences_text}",
            },
            {
                "role": "user",
                "content": (
                    f"Job Title: {job_details.get('title', '')}\n"
                    f"Company: {job_details.get('company', '')}\n"
                    f"Location: {job_details.get('location', '')}\n"
                    f"Description: {description[:4000]}"
                ),
            },
        ]

    def _maybe_create_client(self) -> OpenAI | None:
        api_key = getattr(self.config, "openai_api_key", "")
        if not api_key:
            return None
        try:
            return OpenAI(api_key=api_key)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warning(f"Failed to initialize OpenAI client: {exc}")
            return None

    def _call_llm(
        self, messages: list[dict[str, str]], model: str
    ) -> tuple[float, str]:
        """Call OpenAI using chat.completions or responses for JSON output."""

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
            return float(data.get("score", 0)), data.get("reason", "")

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
            return float(data.get("score", 0)), data.get("reason", "")

        raise RuntimeError("OpenAI client missing chat.completions or responses API")
