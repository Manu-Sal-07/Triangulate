"""The only module in this project that talks to the Gemini API.

Everything else calls through here (CLAUDE.md section 4), so retries, timeouts, JSON
parsing and the degraded-mode contract are defined once instead of being reinvented at
every call site.

The contract this module offers its callers:

  - it raises exactly one exception type, GeminiUnavailable, for every failure mode -
    absent key, timeout, rate limit, transport error, empty response, unparseable JSON;
  - it never raises anything else, so a caller writes one except clause and cannot be
    surprised by a provider-specific error class leaking upward;
  - `available()` answers whether a key exists without making a call, so the app can start
    and serve a deterministic-only review rather than failing at import time.

That is what makes CLAUDE.md section 3.7 implementable: the app never returns a 500 because
a model call failed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from src import config

log = logging.getLogger(__name__)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


class GeminiUnavailable(RuntimeError):
    """Any reason a call could not produce usable JSON. The only exception we raise."""


def available() -> bool:
    """True if a key is configured. Does not make a network call."""
    return config.api_key() is not None


def _client():
    key = config.api_key()
    if not key:
        raise GeminiUnavailable(
            f"{config.API_KEY_ENV} is not set in the environment"
        )
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise GeminiUnavailable(f"google-genai is not installed: {exc}") from exc

    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=int(config.REQUEST_TIMEOUT_SECONDS * 1000),  # SDK wants milliseconds
        ),
    )


def _parse_json(text: str | None) -> Any:
    """Parse a model response that is supposed to be JSON, tolerantly.

    Structured output usually returns bare JSON, but a model that falls back to prose will
    wrap it in a code fence. Stripping the fence is cheap; guessing at anything more
    elaborate is how parsers start silently accepting garbage.
    """
    if not text or not text.strip():
        raise GeminiUnavailable("empty response")
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiUnavailable(f"response was not valid JSON: {exc}") from exc


def _config(schema: dict[str, Any] | None, system: str | None):
    from google.genai import types

    kwargs: dict[str, Any] = {
        "temperature": 0.0,  # extraction is a reading task, not a creative one
        "response_mime_type": "application/json",
    }
    if schema is not None:
        kwargs["response_json_schema"] = schema
    if system:
        kwargs["system_instruction"] = system
    return types.GenerateContentConfig(**kwargs)


def generate_json(
    prompt: str,
    schema: dict[str, Any] | None = None,
    system: str | None = None,
    model: str | None = None,
) -> Any:
    """One JSON-returning call, with retries. Raises GeminiUnavailable on any failure."""
    client = _client()
    last: Exception | None = None

    for attempt in range(1, config.MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=model or config.LLM_MODEL,
                contents=prompt,
                config=_config(schema, system),
            )
            return _parse_json(response.text)
        except GeminiUnavailable as exc:
            last = exc
        except Exception as exc:  # transport, rate limit, server error - all the same to us
            last = exc
        if attempt < config.MAX_ATTEMPTS:
            log.warning("gemini attempt %d/%d failed: %s", attempt, config.MAX_ATTEMPTS, last)
            import time

            time.sleep(config.BACKOFF_SECONDS * attempt)

    raise GeminiUnavailable(f"failed after {config.MAX_ATTEMPTS} attempts: {last}")


async def agenerate_json(
    prompt: str,
    schema: dict[str, Any] | None = None,
    system: str | None = None,
    model: str | None = None,
) -> Any:
    """Async twin of generate_json, so a packet's documents can be read concurrently.

    Concurrency is what makes per-document extraction affordable: four documents read
    independently take about as long as one, and independence is the property that lets
    Python find the contradiction the model would otherwise have smoothed away.
    """
    client = _client()
    last: Exception | None = None

    for attempt in range(1, config.MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=model or config.LLM_MODEL,
                contents=prompt,
                config=_config(schema, system),
            )
            return _parse_json(response.text)
        except GeminiUnavailable as exc:
            last = exc
        except Exception as exc:
            last = exc
        if attempt < config.MAX_ATTEMPTS:
            log.warning("gemini attempt %d/%d failed: %s", attempt, config.MAX_ATTEMPTS, last)
            await asyncio.sleep(config.BACKOFF_SECONDS * attempt)

    raise GeminiUnavailable(f"failed after {config.MAX_ATTEMPTS} attempts: {last}")


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a batch of strings with gemini-embedding-001.

    Batched deliberately: the policy clauses are embedded once and committed, and at request
    time every fact is embedded in a single call rather than one call per fact, which is
    what keeps clause retrieval inside the per-request budget.
    """
    client = _client()
    from google.genai import types

    try:
        response = client.models.embed_content(
            model=config.EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
    except Exception as exc:
        raise GeminiUnavailable(f"embedding call failed: {exc}") from exc

    if not response.embeddings:
        raise GeminiUnavailable("embedding call returned no embeddings")
    return [list(item.values or []) for item in response.embeddings]
