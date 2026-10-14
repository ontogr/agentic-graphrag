"""Checks that the autouse LLM isolation fixture covers the repo-root .env."""

from agrag.agents.settings import AgentLLMSettings
from agrag.ingestion.extract import ExtractionLLMSettings


_CLIENT_LIST = (
    '[{"name": "dotenv", "provider": "openai-generic", "model": "m", '
    '"base_url": "http://example.invalid/v1"}]'
)


def test_dotenv_client_lists_do_not_reach_settings(tmp_path, monkeypatch):
    """Client lists in a repo-root .env do not override the blanked environment."""
    (tmp_path / ".env").write_text(
        f"EXTRACTION_LLM_CLIENTS='{_CLIENT_LIST}'\nAGENT_LLM_CLIENTS='{_CLIENT_LIST}'\n"
    )
    monkeypatch.chdir(tmp_path)

    assert ExtractionLLMSettings().clients == []
    assert AgentLLMSettings().clients == []
