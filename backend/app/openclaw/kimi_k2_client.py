"""Async Kimi K2 client with retries, backoff, and minute-rate limiting."""

from __future__ import annotations

import asyncio
import json
import random
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import KimiK2Settings
from .logging import StructuredLogger


class KimiK2Error(RuntimeError):
    """Raised for Kimi K2 upstream failures."""


class MinuteRateLimiter:
    """Simple queueing minute-based rate limiter."""

    def __init__(self, max_calls_per_minute: int):
        self._max_calls = max_calls_per_minute
        self._calls: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = datetime.now(UTC)
                while self._calls and (now - self._calls[0]) >= timedelta(minutes=1):
                    self._calls.popleft()
                if len(self._calls) < self._max_calls:
                    self._calls.append(now)
                    return
                wait_for = max(0.01, (60.0 - (now - self._calls[0]).total_seconds()))
            await asyncio.sleep(wait_for)


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    left = stripped.find("{")
    right = stripped.rfind("}")
    if left >= 0 and right > left:
        try:
            parsed = json.loads(stripped[left : right + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


class KimiK2Client:
    """Kimi K2 API client with retry/backoff and queue-friendly rate limiting."""

    def __init__(
        self,
        settings: KimiK2Settings,
        *,
        logger: StructuredLogger | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._logger = logger or StructuredLogger("openclaw.kimi_k2_client")
        self._client = httpx.AsyncClient(
            base_url=self.settings.base_url.rstrip("/"),
            timeout=self.settings.timeout_seconds,
            transport=transport,
        )
        self._rate_limiter = MinuteRateLimiter(
            max_calls_per_minute=self.settings.rate_limit_per_minute
        )
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_calls)

    async def close(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        payload_messages = list(messages)
        if system_prompt:
            payload_messages = [{"role": "system", "content": system_prompt}, *payload_messages]

        payload = {
            "model": self.settings.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": self.settings.max_tokens,
        }
        response_payload = await self._request_with_retry(payload)
        choices = response_payload.get("choices", [])
        if not choices:
            raise KimiK2Error("Kimi K2 response missing choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise KimiK2Error("Kimi K2 response content was empty")
        return content

    async def stream_response(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        text = await self.complete(messages)
        for token in text.split():
            yield token + " "

    async def extract_intent(
        self, user_message: str, context: list[dict[str, str]]
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a trading intent parser. Return strict JSON with keys: "
            "command_type, symbol, action, quantity, parameters. Do not add extra text."
        )
        llm_messages = [*context, {"role": "user", "content": user_message}]
        raw = await self.complete(llm_messages, system_prompt=system_prompt, temperature=0.0)
        intent = _extract_json(raw)
        self._logger.info(
            "Intent extracted via Kimi K2", {"intent": intent, "user_message": user_message}
        )
        return intent

    async def _request_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        max_attempts = 3
        delay = 0.5
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(1, max_attempts + 1):
            await self._rate_limiter.acquire()
            async with self._semaphore:
                try:
                    start = datetime.now(UTC)
                    response = await self._client.post(
                        "/chat/completions", json=payload, headers=headers
                    )
                    duration_ms = (datetime.now(UTC) - start).total_seconds() * 1000.0
                    self._logger.info(
                        "Kimi K2 request completed",
                        {
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                            "attempt": attempt,
                        },
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        raise KimiK2Error(f"Retryable Kimi K2 error: HTTP {response.status_code}")
                    response.raise_for_status()
                    return response.json()
                except (httpx.TimeoutException, httpx.NetworkError, KimiK2Error) as exc:
                    if attempt >= max_attempts:
                        self._logger.error(
                            "Kimi K2 request failed after retries", {"error": str(exc)}
                        )
                        raise KimiK2Error(str(exc)) from exc
                    jitter = random.uniform(0.0, 0.25)
                    wait_for = delay + jitter
                    self._logger.warning(
                        "Kimi K2 request retry",
                        {"attempt": attempt, "wait_seconds": round(wait_for, 3), "error": str(exc)},
                    )
                    await asyncio.sleep(wait_for)
                    delay *= 2.0

        raise KimiK2Error("Kimi K2 request exhausted retries unexpectedly")
