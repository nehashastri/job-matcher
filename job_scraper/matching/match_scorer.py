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
    ) -> list:
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
        from openai.types.chat import (
            ChatCompletionSystemMessageParam,
            ChatCompletionUserMessageParam,
        )

        # Strict message order for prompt caching:
        # 0: system message with prompt
        # 1: user message starting with Resume: ...
        return [
            ChatCompletionSystemMessageParam(
                role="system",
                content=prompt,
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content=(
                    f"Resume: {resume_text}\n"
                    f"Job Title: {job_details.get('title', '')}\n"
                    f"Company: {job_details.get('company', '')}\n"
                    f"Location: {job_details.get('location', '')}\n"
                    f"Description: {description[:4000]}"
                ),
            ),
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
                self.logger.info(f"[LLM RESPONSE KWARGS] {response_kwargs}")
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
            # TEMPORARY: Use a simple debug prompt for screening
            # try:
            #     with open("data/LLM_base_score.txt", "r", encoding="utf-8") as f:
            #         base_prompt = f.read().strip()
            # except Exception:
            base_prompt = 'You are a job match scorer. Given a job description and a resume, return a JSON object with the following fields: score (float, 0-10), reason (string), title (string), company (string). Example: {\n  "score": 8.5,\n  "reason": "Strong match on skills and experience.",\n  "title": "Data Scientist",\n  "company": "Acme Corp"\n}\n'

        if rerank_prompt is None:
            try:
                with open("data/LLM_rerank_score.txt", "r", encoding="utf-8") as f:
                    rerank_prompt = f.read().strip()
            except Exception:
                rerank_prompt = base_prompt

        # Always use single-turn prompt and GPT-3.5 for base rank
        messages = self._build_messages(resume_text, job_details, prompt=base_prompt)
        base_model = "gpt-5-nano"
        rerank_model = self.config.openai_model_rerank or "gpt-5-mini"
        # Level-1 (base) settings
        base_temperature = getattr(self.config, "openai_base_temperature", 0.15)
        base_top_p = getattr(self.config, "openai_base_top_p", 0.9)
        # Use higher token limit for gpt-5-nano
        if base_model == "gpt-5-nano":
            base_max_tokens = 2048
        else:
            base_max_tokens = getattr(self.config, "openai_base_max_tokens", 350)
        base_presence_penalty = getattr(self.config, "openai_base_presence_penalty", 0)
        base_frequency_penalty = getattr(
            self.config, "openai_base_frequency_penalty", 0
        )
        # Rerank settings (fallback to global if not set)
        rerank_temperature = getattr(self.config, "openai_temperature", 0.25)
        rerank_top_p = getattr(self.config, "openai_top_p", 0.9)
        # Use higher token limit for gpt-5-nano rerank
        if rerank_model == "gpt-5-nano":
            rerank_max_tokens = 2048
        else:
            rerank_max_tokens = getattr(self.config, "openai_max_tokens", 1200)
        trigger = getattr(self.config, "job_match_rerank_trigger", 8)

        try:
            first_score, first_reason, inferred_title, inferred_company = (
                self._call_llm(
                    messages,
                    base_model,
                    base_temperature,
                    base_top_p,
                    base_max_tokens,
                    base_presence_penalty,
                    base_frequency_penalty,
                    effort="minimal",
                )
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
                # Always use single-turn prompt and latest GPT-4 for rerank
                rerank_messages = self._build_messages(
                    resume_text, job_details, prompt=rerank_prompt
                )
                self.logger.info(f"[RERANK] Using model for rerank: {rerank_model}")
                rerank_score, reason_rerank, _, _ = self._call_llm(
                    rerank_messages,
                    rerank_model,  # Use gpt-5-mini for rerank
                    rerank_temperature,
                    rerank_top_p,
                    rerank_max_tokens,
                    0,
                    0,
                    effort="low",
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

    def _call_llm(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.25,
        top_p: float = 0.9,
        max_tokens: int = 1200,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        effort: str = "minimal",
    ) -> tuple:
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
            completion_kwargs = dict(
                model=model,
                messages=typed_messages,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            # Only set response_format if model is not gpt-5-nano
            if not model.startswith("gpt-5-nano"):
                completion_kwargs["response_format"] = {"type": "json_object"}
            # Reasoning Models (gpt-5, gpt-4.1): Use max_completion_tokens AND reasoning_effort.
            # Modern Standard Models (gpt-4-turbo): Use max_completion_tokens ONLY.
            # Legacy Models: Use max_tokens and temperature/top_p.
            if model.startswith("gpt-5") or model.startswith("gpt-4.1"):
                completion_kwargs["max_completion_tokens"] = max_tokens
                completion_kwargs["reasoning_effort"] = effort
            elif model.startswith("gpt-4-turbo"):
                completion_kwargs["max_completion_tokens"] = max_tokens
                completion_kwargs["temperature"] = temperature
            else:
                completion_kwargs["max_tokens"] = max_tokens
                completion_kwargs["temperature"] = temperature
            resp = client.chat.completions.create(**completion_kwargs)
            content = resp.choices[0].message.content if resp.choices else "{}"
            self.logger.info(f"[LLM RAW RESPONSE] {content}")
            data = json.loads(content or "{}")
            return (
                float(data.get("score", 0)),
                data.get("reason", ""),
                data.get("title", ""),
                data.get("company", ""),
            )

        # Fallback to responses API (matches mocks/tests style)
        if hasattr(client, "responses"):
            response_kwargs = dict(
                model=model,
                messages=typed_messages,
                response_format={"type": "json_object"},
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            if not (
                model.startswith("gpt-5")
                or model.startswith("gpt-4.1")
                or model.startswith("gpt-4-turbo")
            ):
                response_kwargs["top_p"] = top_p
            if model.startswith("gpt-5") or model.startswith("gpt-4.1"):
                response_kwargs["max_completion_tokens"] = max_tokens
                response_kwargs["reasoning"] = {"effort": effort}
                # Omit temperature and top_p for gpt-5/gpt-4.1
            elif model.startswith("gpt-4-turbo"):
                response_kwargs["max_completion_tokens"] = max_tokens
                # Do NOT add reasoning for gpt-4-turbo
            else:
                response_kwargs["max_tokens"] = max_tokens
                response_kwargs["temperature"] = temperature
            response = client.responses.create(**response_kwargs)

            # Capture the usage object
            usage = getattr(response, "usage", None)
            if usage:
                # Safely access prompt_tokens_details (it might be None for some models)
                prompt_details = getattr(usage, "prompt_tokens_details", None)
                cached_tokens = (
                    getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0
                )
                self.logger.info(
                    f"LLM Usage Stats - Model: {model} | "
                    f"Total: {getattr(usage, 'total_tokens', '?')} | "
                    f"Prompt: {getattr(usage, 'prompt_tokens', '?')} | "
                    f"Cached: {cached_tokens} | "
                    f"Completion: {getattr(usage, 'completion_tokens', '?')}"
                )
                if cached_tokens > 0:
                    savings = (cached_tokens / getattr(usage, "prompt_tokens", 1)) * 100
                    self.logger.info(
                        f"✨ Prompt Caching saved {savings:.1f}% of input tokens!"
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
