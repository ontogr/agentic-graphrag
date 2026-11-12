"""Helpers for checking live LLM access before provider-backed tests run."""

import hashlib

import httpx
import pytest


_PROBE_CACHE: dict[bytes, str | None] = {}


def _cache_key(base_url: str, api_key: str | None, model: str) -> bytes:
    """Return a provider-config key without retaining the API key in the cache."""
    config = "\0".join((base_url.rstrip("/"), api_key or "", model))
    return hashlib.sha256(config.encode()).digest()


def probe_live_llm(
    base_url: str,
    api_key: str | None,
    model: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Skip on unavailable access, accept HTTP 429 as reachable, and raise others.

    An HTTP 200 or 429 response shows that the endpoint is up and the key is
    accepted, so the probe passes. A 429 means the endpoint has no spare request
    capacity right now. The probe checks access only, so it does not retry or
    sleep on a 429. HTTP 401 and 402 skip with a reason. Connection errors and
    timeouts skip and are probed again on later checks. Other statuses raise.
    Reachable (200 or 429) and HTTP 401/402 default-transport results are cached
    by endpoint, model, and API-key hash. Injected transports bypass the cache
    for isolated tests.
    """
    cache_key = _cache_key(base_url, api_key, model) if transport is None else None
    if cache_key is not None and cache_key in _PROBE_CACHE:
        reason = _PROBE_CACHE[cache_key]
        if reason is not None:
            pytest.skip(reason)
        return

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with httpx.Client(
            base_url=f"{base_url.rstrip('/')}/",
            headers=headers,
            timeout=15.0,
            transport=transport,
        ) as client:
            response = client.post(
                "chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Reply with OK."}],
                    "max_tokens": 1,
                },
            )
    except (httpx.ConnectError, httpx.TimeoutException) as error:
        detail = (
            "connection failed"
            if isinstance(error, httpx.ConnectError)
            else "request timed out"
        )
        reason = f"LLM provider unavailable ({detail})"
        pytest.skip(reason)

    reason = {
        401: "LLM provider unavailable (HTTP 401; credentials rejected)",
        402: "LLM provider unavailable (HTTP 402; provider credits required)",
    }.get(response.status_code)
    if reason is not None:
        if cache_key is not None:
            _PROBE_CACHE[cache_key] = reason
        pytest.skip(reason)
    # A 429 shows the key and endpoint work, so it does not fail the status check.
    if response.status_code != 429:
        response.raise_for_status()
    if cache_key is not None:
        _PROBE_CACHE[cache_key] = None
