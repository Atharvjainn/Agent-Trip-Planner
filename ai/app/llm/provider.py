"""
ai/AGENT.md "LLM usage":
  - Call only through llm/provider.py: `await llm.structured(task, prompt, schema=PydanticModel)`.
  - Order: Gemini -> OpenAI -> Grok. On timeout (20s), rate limit, or
    schema-invalid output, try the next provider once. If all fail, the
    graph uses its deterministic fallback.
  - Always request structured output bound to a Pydantic model. Never
    parse free text with regex.
  - Log per call: task, provider, latency, token counts. No user PII in logs.

This module never raises past `structured()` for the "all providers
failed" case — it raises LLMAllProvidersFailed, which every graph node
catches to take its deterministic fallback branch (ai/AGENT.md: "Demo
reliability beats completeness", root AGENTS.md §10.7).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

logger = logging.getLogger("services.ai.llm")

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMAllProvidersFailed(RuntimeError):
    def __init__(self, task: str, attempts: list[str]) -> None:
        super().__init__(f"all LLM providers failed for task={task!r}: {attempts}")
        self.task = task
        self.attempts = attempts


class ProviderUnavailable(RuntimeError):
    """Raised by a provider implementation when it can't even attempt the
    call (no API key configured, etc). Counts as one failed attempt."""


class LLMProviderBackend(Protocol):
    name: str

    async def complete_json(self, *, prompt: str, system: str | None, timeout_seconds: float) -> str:
        """Return raw text that should be a JSON object. Providers are
        asked for structured/JSON-mode output where the underlying API
        supports it, but final validation always happens in this module,
        never by trusting the provider."""
        ...


class GeminiBackend:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete_json(self, *, prompt: str, system: str | None, timeout_seconds: float) -> str:
        if not self._settings.gemini_api_key:
            raise ProviderUnavailable("GEMINI_API_KEY not configured")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={self._settings.gemini_api_key}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class OpenAIBackend:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete_json(self, *, prompt: str, system: str | None, timeout_seconds: float) -> str:
        if not self._settings.openai_api_key:
            raise ProviderUnavailable("OPENAI_API_KEY not configured")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class GrokBackend:
    name = "grok"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete_json(self, *, prompt: str, system: str | None, timeout_seconds: float) -> str:
        if not self._settings.grok_api_key:
            raise ProviderUnavailable("GROK_API_KEY not configured")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._settings.grok_api_key}"},
                json={
                    "model": "grok-2-latest",
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class LLMProvider:
    """Orchestrates the Gemini -> OpenAI -> Grok fallback chain. One retry
    per provider, then move on. Construct with explicit `backends` in
    tests to avoid any real network calls."""

    def __init__(
        self, backends: list[LLMProviderBackend] | None = None, settings: Settings | None = None
    ) -> None:
        settings = settings or get_settings()
        self._settings = settings
        self._backends = backends or [
            GeminiBackend(settings),
            OpenAIBackend(settings),
            GrokBackend(settings),
        ]

    async def structured(
        self,
        task: str,
        prompt: str,
        schema: type[ModelT],
        *,
        system: str | None = None,
    ) -> ModelT:
        attempts: list[str] = []
        for backend in self._backends:
            for retry in range(2):  # one retry per provider, per AGENT.md
                start = time.monotonic()
                try:
                    raw = await backend.complete_json(
                        prompt=prompt, system=system, timeout_seconds=self._settings.llm_timeout_seconds
                    )
                    parsed = schema.model_validate(json.loads(raw))
                    latency_ms = int((time.monotonic() - start) * 1000)
                    logger.info(
                        "llm_call_ok",
                        extra={
                            "task": task,
                            "provider": backend.name,
                            "latency_ms": latency_ms,
                            "retry": retry,
                        },
                    )
                    return parsed
                except (ProviderUnavailable, httpx.TimeoutException, httpx.HTTPStatusError,
                        json.JSONDecodeError, ValidationError) as exc:
                    latency_ms = int((time.monotonic() - start) * 1000)
                    logger.warning(
                        "llm_call_failed",
                        extra={
                            "task": task,
                            "provider": backend.name,
                            "latency_ms": latency_ms,
                            "retry": retry,
                            "error_type": type(exc).__name__,
                        },
                        exc_info=True,
                    )
                    attempts.append(f"{backend.name}#{retry}:{type(exc).__name__}")
                    if isinstance(exc, ProviderUnavailable):
                        break  # no point retrying a provider with no key configured
                    continue
        raise LLMAllProvidersFailed(task, attempts)
