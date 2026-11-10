"""Helpers for checking live LLM access before provider-backed tests run."""

import httpx
import pytest


def probe_live_llm(
    base_url: str,
    api_key: str | None,
    model: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Skip on HTTP 401 or 402 and raise other failures."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
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

    if response.status_code == 401:
        pytest.skip("LLM provider unavailable (HTTP 401; credentials rejected)")
    if response.status_code == 402:
        pytest.skip("LLM provider unavailable (HTTP 402; provider credits required)")
    response.raise_for_status()
