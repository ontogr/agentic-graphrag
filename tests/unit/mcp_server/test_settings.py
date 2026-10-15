"""Unit tests for the scope parsing of the MCP server settings.

The settings read only their own arguments here, so the tests run with no
environment variables and no .env file.
"""

import pytest
from pydantic import ValidationError

from agrag.mcp_server.settings import McpServerSettings


class TestMcpServerSettingsScope:
    """The scope of the settings is the set of keys that the server may read."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("privacy_qa/Keep.txt", {"privacy_qa/Keep.txt"}),
            (" a/one.txt , b/two.txt ,", {"a/one.txt", "b/two.txt"}),
            ("a/one.txt,a/one.txt", {"a/one.txt"}),
        ],
    )
    def test_scope_holds_each_trimmed_non_blank_key_once(
        self, raw: str, expected: set[str]
    ) -> None:
        """Keep each trimmed key once and drop blank entries."""
        settings = McpServerSettings(scope_document_keys=raw, _env_file=None)

        assert settings.scope == frozenset(expected)

    @pytest.mark.parametrize("raw", ["", "   ", " , ,"])
    def test_refuses_a_scope_that_names_no_key(self, raw: str) -> None:
        """Refuse a scope with no document key, so the server cannot start open."""
        with pytest.raises(ValidationError, match="at least one document key"):
            McpServerSettings(scope_document_keys=raw, _env_file=None)

    def test_refuses_a_missing_scope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Refuse a server started with no scope variable."""
        monkeypatch.delenv("AGRAG_MCP_SCOPE_DOCUMENT_KEYS", raising=False)

        with pytest.raises(ValidationError, match="at least one document key"):
            McpServerSettings(_env_file=None)
