"""CLI startup refuses invalid scope or missing optional dependencies."""

import importlib.util

import pytest

from agrag.mcp_server.__main__ import main
from agrag.mcp_server.errors import McpServerMissingExtraError


class TestStartupRefusal:
    """Startup errors are actionable and do not write to the protocol stream."""

    def test_empty_scope_exits_with_settings_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Reject an empty scope before trying to connect to a graph store."""
        monkeypatch.setenv("MCP_SCOPE_DOCUMENT_KEYS", "")

        with pytest.raises(SystemExit) as raised:
            main()

        captured = capsys.readouterr()
        assert raised.value.code == 2
        assert captured.out == ""
        assert "agrag-mcp: invalid settings:" in captured.err
        assert "at least one document key" in captured.err

    def test_missing_mcp_extra_names_the_install_command(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Tell the operator which extra is missing without starting the server."""
        find_spec = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util,
            "find_spec",
            lambda name: None if name == "mcp" else find_spec(name),
        )

        with pytest.raises(McpServerMissingExtraError) as raised:
            main()

        assert raised.value.extra == "mcp"
        assert "pip install 'agentic-graphrag[mcp]'" in str(raised.value)
        assert capsys.readouterr().out == ""
