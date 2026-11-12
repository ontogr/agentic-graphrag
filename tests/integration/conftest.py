"""Fixtures for live LLM integration tests, and the offline default for the rest.

A test that requests a live fixture keeps its endpoint settings. Every other
integration test has the endpoint settings blanked: LLM_BASE_URL, LLM_API_KEY
and LLM_MODEL_ID, and their AGENT_LLM_* and EVAL_JUDGE_* counterparts, are set
to empty strings, so the settings readers see them as unset. EXTRACTION_LLM_CLIENTS
is not blanked.
"""

from collections.abc import Generator

import pytest

from tests.integration._live_llm import probe_live_llm


# An empty value makes the settings readers treat the variable as unset. It
# also stops load_dotenv (override=False) from refilling it from .env.
_PROVIDER_ENV_NAMES = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL_ID",
    "AGENT_LLM_BASE_URL",
    "AGENT_LLM_API_KEY",
    "AGENT_LLM_MODEL_ID",
    "EVAL_JUDGE_BASE_URL",
    "EVAL_JUDGE_API_KEY",
    "EVAL_JUDGE_MODEL_ID",
)
_LIVE_FIXTURES = frozenset(
    {
        "live_extraction_llm",
        "live_agent_llm",
        "live_eval_judge_llm",
        "llm_env",
        "agent_llm_env",
    }
)
# Eval tests request live fixtures with getfixturevalue, so pytest does not
# list them in fixturenames. The eval workflows also set their own env.
_EVAL_TREE = "/tests/integration/eval/"


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


def _keeps_provider_env(item: pytest.Item) -> bool:
    """Return True when the item must see the provider env as configured."""
    if _EVAL_TREE in item.path.as_posix():
        return True
    return bool(_LIVE_FIXTURES.intersection(item.fixturenames))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, object, object]:
    """Blank the provider env for a non-live item, around its whole protocol.

    The wrapper runs before any fixture of the item is built, so module-scoped
    fixtures such as ``noop_graph`` see the blank env too. The env is restored
    after teardown, so the next item starts from the shell values again.
    """
    if _keeps_provider_env(item):
        return (yield)
    patch = pytest.MonkeyPatch()
    for name in _PROVIDER_ENV_NAMES:
        patch.setenv(name, "")
    try:
        return (yield)
    finally:
        patch.undo()
