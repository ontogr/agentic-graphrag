"""Integration tests for the stdio server started as a real subprocess.

The first test starts the server through the SDK stdio client, with the server
command wrapped by ``_stdio_tee.py``. The wrapper keeps a copy of the server's
stdout bytes, so the test can check every line of the protocol stream. Stdio
clients skip malformed lines without failing, so the copy is the only reliable
check. Logs go to stderr and are not checked here.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from agrag.common.data_models.evidence import (
    CitationResult,
    CitationVerdict,
    EvidenceSearchResult,
    FetchResult,
    FetchStatus,
)
from tests.integration.retrieval.evidence._corpus import KEEP_TEXT
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_REPO_ROOT = Path(__file__).resolve().parents[4]
_TEE = Path(__file__).with_name("_stdio_tee.py")
_QUERY = "keep upload activity database"


def _server_environment(
    scope_keys: str, graph_environment: dict[str, str]
) -> dict[str, str]:
    """Return the environment of a server process, with a given scope."""
    return {
        **os.environ,
        **graph_environment,
        "PYTHONPATH": str(_REPO_ROOT),
        "MCP_SCOPE_DOCUMENT_KEYS": scope_keys,
        "OPENAI_API_KEY": "",
        "LLM_API_KEY": "",
        "LLM_BASE_URL": "",
        "LLM_MODEL_ID": "",
    }


class TestStdioSession:
    """A real stdio session answers every call with clean protocol output."""

    async def test_full_session_writes_only_protocol_lines_to_stdout(
        self, evidence_env: EvidenceEnv, tmp_path: Path
    ) -> None:
        """Check every stdout line of a session that lists, searches and fetches."""
        env = evidence_env
        stdout_log = tmp_path / "server_stdout.log"
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(_TEE), str(stdout_log)],
            env=_server_environment(f"{env.keep},{env.harbor}", env.server_environment),
            cwd=str(_REPO_ROOT),
        )

        async with Client(parameters, raise_exceptions=True) as client:
            listing = await client.list_tools()
            search = await client.call_tool(
                "search_evidence", {"query": _QUERY, "mode": "lexical"}
            )
            hits = EvidenceSearchResult.model_validate(search.structured_content).hits
            fetched = await client.call_tool(
                "fetch_evidence", {"evidence_ids": [hits[0].evidence_id]}
            )
            outcome = FetchResult.model_validate(fetched.structured_content).outcomes[0]
            checked = await client.call_tool(
                "check_citations", {"evidence_ids": [hits[0].evidence_id]}
            )

        assert sorted(tool.name for tool in listing.tools) == [
            "check_citations",
            "entity_search",
            "explore_relationships",
            "fetch_evidence",
            "navigate_document_tree",
            "search_evidence",
            "search_themes",
        ]
        assert hits[0].document_key == env.keep
        assert outcome.status is FetchStatus.OK
        assert outcome.text is not None
        assert outcome.text in KEEP_TEXT
        verdicts = CitationResult.model_validate(checked.structured_content).checks
        assert verdicts[0].verdict is CitationVerdict.VALID

        lines = stdout_log.read_bytes().splitlines()
        assert lines
        for line in lines:
            assert json.loads(line)["jsonrpc"] == "2.0"


class TestStdioRefusal:
    """The server refuses to start without a scope and writes nothing to stdout."""

    def test_empty_scope_exits_non_zero_with_message_and_no_stdout(self) -> None:
        """Exit non-zero with a stderr message and empty stdout for an empty scope."""
        completed = subprocess.run(
            [sys.executable, "-m", "agrag.mcp_server"],
            env=_server_environment("", {}),
            cwd=str(_REPO_ROOT),
            capture_output=True,
            timeout=120,
            check=False,
        )

        assert completed.returncode != 0
        assert completed.stdout == b""
        assert b"at least one document key" in completed.stderr
