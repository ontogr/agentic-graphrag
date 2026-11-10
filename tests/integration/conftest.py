"""Fixtures for live LLM integration tests."""

import pytest

from tests.integration._live_llm import probe_live_llm


@pytest.fixture
def live_extraction_llm() -> None:
    """Check the shared extraction endpoint before a provider-backed test."""
    from agrag.ingestion.extract import ExtractionLLMSettings  # noqa: PLC0415

    try:
        settings = ExtractionLLMSettings.from_openai_compatible_env()
    except RuntimeError:
        return

    client = settings.clients[0]
    if not client.base_url:
        return
    api_key = client.api_key.get_secret_value() if client.api_key else None
    probe_live_llm(client.base_url, api_key, client.model)


@pytest.fixture
def live_agent_llm() -> None:
    """Check the configured agent endpoint before a provider-backed test."""
    from agrag.agents.settings import AgentLLMSettings  # noqa: PLC0415

    client = AgentLLMSettings.from_openai_compatible_env().clients[0]
    if not client.base_url:
        return
    api_key = client.api_key.get_secret_value() if client.api_key else None
    probe_live_llm(client.base_url, api_key, client.model)


@pytest.fixture
def live_eval_judge_llm() -> None:
    """Check the configured evaluation judge endpoint before a live test."""
    from agrag.eval.settings import EvalJudgeSettings  # noqa: PLC0415

    try:
        client = EvalJudgeSettings.from_openai_compatible_env().client
    except ValueError:
        return
    if not client.base_url:
        return
    api_key = client.api_key.get_secret_value() if client.api_key else None
    probe_live_llm(client.base_url, api_key, client.model)
