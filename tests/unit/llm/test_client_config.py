"""Check that LLM client credentials stay hidden from printed config."""

from agrag.llm.client_config import LLMClientConfig


def test_repr_hides_client_api_key() -> None:
    """A client config does not print its API key."""
    config = LLMClientConfig(
        name="judge",
        provider="openai-generic",
        model="model",
        api_key="xy" + "z123",
    )

    assert "xyz123" not in repr(config)
    assert "xyz123" not in str(config)


def test_empty_credential_is_falsy() -> None:
    """An empty credential keeps provider-test skip guards effective."""
    config = LLMClientConfig(
        name="local", provider="openai-generic", model="model", api_key=""
    )

    assert not config.api_key
