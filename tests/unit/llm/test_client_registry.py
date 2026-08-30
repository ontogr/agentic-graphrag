"""Tests for building a BAML ClientRegistry from LLMClientConfig."""

import pytest

from agrag.llm.client_config import LLMClientConfig, RetryConfig
from agrag.llm.client_registry import build_client_registry


class FakeClientRegistry:
    """Records calls so the builder can be tested without a real BAML runtime."""

    def __init__(self) -> None:
        """Start with no registered clients and no primary."""
        self.added: list[tuple[str, str, dict]] = []
        self.retry_policies: list[str | None] = []
        self.primary: str | None = None

    def add_llm_client(
        self, *, name: str, provider: str, options: dict, retry_policy=None
    ) -> None:
        """Record a registered client."""
        self.added.append((name, provider, options))
        self.retry_policies.append(retry_policy)

    def set_primary(self, primary: str) -> None:
        """Record the primary client name."""
        self.primary = primary


def _client(name: str, provider: str = "openai") -> LLMClientConfig:
    return LLMClientConfig(name=name, provider=provider, model="m")


class TestBuildClientRegistry:
    """The builder registers clients and picks a primary per strategy."""

    def test_single_sets_the_one_client_primary(self, monkeypatch) -> None:
        """With one client, it becomes the primary and no composite is made."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        registry = build_client_registry([_client("only")], strategy="single")
        assert registry is fake
        assert [name for name, _, _ in fake.added] == ["only"]
        assert fake.primary == "only"

    def test_fallback_registers_a_composite_over_all_names(self, monkeypatch) -> None:
        """Fallback adds one composite client and makes it primary."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        build_client_registry([_client("a"), _client("b")], strategy="fallback")
        names = [name for name, _, _ in fake.added]
        assert names == ["a", "b", "_agrag_composite"]
        assert fake.primary == "_agrag_composite"

    def test_round_robin_registers_a_composite_over_all_names(
        self, monkeypatch
    ) -> None:
        """Round-robin adds one composite client and makes it primary."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        build_client_registry([_client("a"), _client("b")], strategy="round_robin")
        names = [name for name, _, _ in fake.added]
        assert names == ["a", "b", "_agrag_composite"]
        assert fake.primary == "_agrag_composite"

    def test_empty_clients_raises_value_error(self, monkeypatch) -> None:
        """An empty client list is rejected."""
        monkeypatch.setattr("baml_py.ClientRegistry", FakeClientRegistry)
        with pytest.raises(ValueError):
            build_client_registry([])

    def test_openai_generic_passes_base_url_and_key(self, monkeypatch) -> None:
        """An openai-generic client forwards base_url and api_key to options."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        client = LLMClientConfig(
            name="g",
            provider="openai-generic",
            model="llm",
            api_key="secret",
            base_url="http://localhost:1234/v1",
        )
        build_client_registry([client], strategy="single")
        _, provider, options = fake.added[0]
        assert provider == "openai-generic"
        assert options["base_url"] == "http://localhost:1234/v1"
        assert options["api_key"] == "secret"
        assert options["model"] == "llm"

    def test_no_retry_attaches_no_retry_policy(self, monkeypatch) -> None:
        """With retry=None, no retry_policy name is passed to add_llm_client."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        build_client_registry([_client("only")], strategy="single")
        assert fake.retry_policies == [None]

    def test_default_retry_attaches_the_default_policy_to_every_client(
        self, monkeypatch
    ) -> None:
        """RetryConfig()'s defaults reach every client as AgragDefaultRetry."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        build_client_registry(
            [_client("a"), _client("b")], strategy="single", retry=RetryConfig()
        )
        assert fake.retry_policies == ["AgragDefaultRetry", "AgragDefaultRetry"]

    def test_non_default_retry_raises_instead_of_reaching_add_llm_client(
        self, monkeypatch
    ) -> None:
        """A non-default RetryConfig is rejected, not silently passed through."""
        fake = FakeClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: fake)
        with pytest.raises(ValueError, match="no matching BAML retry_policy"):
            build_client_registry(
                [_client("only")],
                strategy="single",
                retry=RetryConfig(max_retries=5),
            )
        assert fake.added == []
