"""A local OpenAI-compatible server for the LLM span tests.

Adapted from the ``baml_collector_spike.py`` component test: the path prefix
picks the response mode, so a test can serve a fixed reply, a rate-limit, or a
server error with real HTTP traffic and no network access. The real BAML
runtime and a real ``ChatOpenAI`` both talk to it, so nothing below the HTTP
boundary is mocked.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SECRET = "sk-span-contract-sentinel-key"

# The counts the fake endpoint reports, so a test can assert exact token
# attributes on a real span.
PROMPT_TOKENS = 11
COMPLETION_TOKENS = 7


def _reply_for(mode: str) -> str:
    """Return reply text that satisfies the BAML function for that mode."""
    return {
        "html": "<html>Bad Gateway</html>",
        "extract": "[]",
        "verify": "[]",
        "cypher": "MATCH (n) RETURN n",
    }.get(mode, "merged description")


class _Handler(BaseHTTPRequestHandler):
    """Answer chat completions according to the mode in the request path."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Stay quiet; pytest captures stderr."""

    def do_POST(self) -> None:  # noqa: N802
        """Serve the reply the path prefix names."""
        mode = self.path.split("/")[1]
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.received.append(body)  # type: ignore[attr-defined]
        if mode == "500":
            payload = json.dumps({"error": {"message": "boom"}}).encode()
            self.send_response(500)
        else:
            reply: dict[str, Any] = {
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                # A served name that differs from the requested one, so a test
                # can tell which of the two the span recorded.
                "model": f"{body.get('model')}-served",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": _reply_for(mode)},
                        "finish_reason": "stop",
                    }
                ],
            }
            if mode != "nousage":
                reply["usage"] = {
                    "prompt_tokens": PROMPT_TOKENS,
                    "completion_tokens": COMPLETION_TOKENS,
                    "total_tokens": PROMPT_TOKENS + COMPLETION_TOKENS,
                }
            payload = json.dumps(reply).encode()
            self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class LocalLLM:
    """A running fake endpoint and the client registry pointing at it."""

    def __init__(self) -> None:
        """Start the server on an ephemeral port."""
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.received = []  # type: ignore[attr-defined]
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        """Return the server root, without a mode prefix."""
        return f"http://127.0.0.1:{self.port}"

    def url(self, mode: str = "ok") -> str:
        """Return the OpenAI-compatible base URL serving that mode."""
        return f"{self.base_url}/{mode}/v1"

    @property
    def received(self) -> list[dict[str, Any]]:
        """Return every request body the server saw, in order."""
        return self._server.received  # type: ignore[attr-defined]

    def close(self) -> None:
        """Stop the server and release its port."""
        self._server.shutdown()
        self._server.server_close()


def registry(base_url: str, *, name: str = "primary") -> Any:
    """Return a BAML client registry with one client at the given URL.

    Args:
        base_url: The OpenAI-compatible base URL the client should call.
        name: The client name, so a test can tell clients apart.

    Returns:
        A ``ClientRegistry`` with one ``openai-generic`` client as primary.
    """
    from baml_py import ClientRegistry  # noqa: PLC0415

    reg = ClientRegistry()
    reg.add_llm_client(
        name=name,
        provider="openai-generic",
        options={
            "base_url": base_url,
            "model": "requested-model",
            "api_key": SECRET,
        },
    )
    reg.set_primary(name)
    return reg


def fallback_registry(local: LocalLLM) -> Any:
    """Return a registry whose primary fails and whose fallback serves.

    BAML only tries the second client when a composite client composes them
    under a fallback strategy, so both are registered and a composite is made
    primary.
    """
    from baml_py import ClientRegistry  # noqa: PLC0415

    reg = ClientRegistry()
    for name, mode in (("primary", "500"), ("secondary", "ok")):
        reg.add_llm_client(
            name=name,
            provider="openai-generic",
            options={
                "base_url": local.url(mode),
                "model": "requested-model",
                "api_key": SECRET,
            },
        )
    reg.add_llm_client(
        name="_composite",
        provider="fallback",
        options={"strategy": ["primary", "secondary"]},
    )
    reg.set_primary("_composite")
    return reg


def env_for(local: LocalLLM, monkeypatch: Any, mode: str = "ok") -> None:
    """Point the env-backed settings at the fake endpoint.

    Args:
        local: The running fake endpoint.
        monkeypatch: The active pytest monkeypatch fixture.
        mode: The response mode the base URL selects.
    """
    monkeypatch.setenv("LLM_BASE_URL", local.url(mode))
    monkeypatch.setenv("LLM_MODEL_ID", "requested-model")
    monkeypatch.setenv("LLM_API_KEY", SECRET)


def dead_base_url() -> str:
    """Return a base URL on a port nothing listens on."""
    import socket  # noqa: PLC0415

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/ok/v1"


def span_tree_path(name: str) -> Path:
    """Return the artifact path for a captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "llm"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def write_span_tree(path: Path, spans: Any) -> None:
    """Write the captured span tree artifact, verifying the round trip.

    The prompt and response bodies stay out of the artifact, which is checked
    into a report directory; the span names, parents, statuses and non-text
    attributes are what a reader needs.
    """
    payload: dict[str, Any] = {
        "spans": [
            {
                "id": f"{span.context.span_id:016x}",
                "parent": f"{span.parent.span_id:016x}" if span.parent else None,
                "name": span.name,
                "kind": (span.attributes or {}).get("openinference.span.kind"),
                "status": span.status.status_code.name,
                "attributes": {
                    key: value
                    for key, value in (span.attributes or {}).items()
                    if key not in ("input.value", "output.value")
                },
            }
            for span in spans
        ]
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    assert json.loads(path.read_text()) == payload
