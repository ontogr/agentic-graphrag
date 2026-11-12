"""Tests for build_client_registry in agrag.llm.client_registry.

Patches ``baml_py.ClientRegistry`` with a MockClientRegistry that records
added clients and the chosen primary, so no real BAML runtime is needed.
Covers "fallback" and "round_robin" both registering a composite client over
every name and making it primary, and an empty client list raising ValueError.
Also covers the per-client request timeout the registry hands to BAML. The
integration tests cannot reach the limits above 300 seconds or the zero value
that removes the limit, because they would have to wait it out.
"""

import pytest

from agrag.llm.client_config import LLMClientConfig
from agrag.llm.client_registry import build_client_registry


class MockClientRegistry:
    """Records calls so the builder can be tested without a real BAML runtime."""

    def __init__(self) -> None:
        """Start with no registered clients and no primary."""
        self.added: list[tuple[str, str, dict]] = []
        self.primary: str | None = None

    def add_llm_client(self, *, name: str, provider: str, options: dict) -> None:
        """Record a registered client."""
        self.added.append((name, provider, options))

    def set_primary(self, primary: str) -> None:
        """Record the primary client name."""
        self.primary = primary


def _client(name: str, provider: str = "openai") -> LLMClientConfig:
    return LLMClientConfig(name=name, provider=provider, model="m")


class TestBuildClientRegistry:
    """The builder registers clients and picks a primary per strategy."""

    @staticmethod
    def test_registry_receives_unwrapped_api_key(monkeypatch) -> None:
        """The BAML registry receives a plain API key string."""
        mock = MockClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: mock)
        secret = "x" * 5

        build_client_registry(
            [
                LLMClientConfig(
                    name="secured",
                    provider="openai",
                    model="m",
                    api_key=secret,
                )
            ],
            request_timeout_ms=300_000,
        )

        assert mock.added[0][2]["api_key"] == secret

    def test_fallback_registers_a_composite_over_all_names(self, monkeypatch) -> None:
        """Fallback adds one composite client and makes it primary."""
        mock = MockClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: mock)
        build_client_registry(
            [_client("a"), _client("b")],
            strategy="fallback",
            request_timeout_ms=300_000,
        )
        names = [name for name, _, _ in mock.added]
        assert names == ["a", "b", "_agrag_composite"]
        assert mock.primary == "_agrag_composite"

    def test_round_robin_registers_a_composite_over_all_names(
        self, monkeypatch
    ) -> None:
        """Round-robin adds one composite client and makes it primary."""
        mock = MockClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: mock)
        build_client_registry(
            [_client("a"), _client("b")],
            strategy="round_robin",
            request_timeout_ms=300_000,
        )
        names = [name for name, _, _ in mock.added]
        assert names == ["a", "b", "_agrag_composite"]
        assert mock.primary == "_agrag_composite"

    def test_empty_clients_raises_value_error(self, monkeypatch) -> None:
        """An empty client list is rejected."""
        monkeypatch.setattr("baml_py.ClientRegistry", MockClientRegistry)
        with pytest.raises(ValueError):
            build_client_registry([], request_timeout_ms=300_000)

    @staticmethod
    def test_duplicate_client_names_raise_before_registration(monkeypatch) -> None:
        """Duplicate names are rejected without adding either client."""
        mock = MockClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: mock)

        with pytest.raises(ValueError, match="primary"):
            build_client_registry(
                [_client("primary"), _client("primary")], request_timeout_ms=300_000
            )

        assert mock.added == []

    @staticmethod
    @pytest.mark.parametrize(
        ("strategy", "client_count", "request_timeout_ms", "expected_ms"),
        [
            ("single", 1, 300_000, 300_000),
            ("single", 1, 900_000, 900_000),
            ("round_robin", 2, 600_000, 600_000),
            ("fallback", 2, 600_000, 300_000),
            ("fallback", 3, 1_000, 334),
            ("fallback", 2, 1, 1),
            ("single", 1, 0, 0),
            ("fallback", 2, 0, 0),
        ],
    )
    def test_each_client_gets_its_share_of_the_request_timeout(
        monkeypatch, strategy, client_count, request_timeout_ms, expected_ms
    ) -> None:
        """BAML gets a per-client limit: the whole value, or a fallback's share."""
        mock = MockClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: mock)

        build_client_registry(
            [_client(f"c{index}") for index in range(client_count)],
            strategy=strategy,
            request_timeout_ms=request_timeout_ms,
        )

        limits = [
            options["http"]["request_timeout_ms"]
            for name, _, options in mock.added
            if name != "_agrag_composite"
        ]
        assert limits == [expected_ms] * client_count

    @staticmethod
    def test_explicit_http_options_win_and_are_left_unchanged(monkeypatch) -> None:
        """A client's own timeout wins, and its http dict is not modified."""
        mock = MockClientRegistry()
        monkeypatch.setattr("baml_py.ClientRegistry", lambda: mock)
        partial = {"connect_timeout_ms": 1_000}
        configs = [
            LLMClientConfig(
                name="explicit",
                provider="openai",
                model="m",
                options={"http": {"request_timeout_ms": 5_000, **partial}},
            ),
            LLMClientConfig(
                name="partial", provider="openai", model="m", options={"http": partial}
            ),
        ]

        build_client_registry(configs, request_timeout_ms=60_000)

        assert mock.added[0][2]["http"] == {"request_timeout_ms": 5_000, **partial}
        assert mock.added[1][2]["http"] == {"request_timeout_ms": 60_000, **partial}
        assert partial == {"connect_timeout_ms": 1_000}
