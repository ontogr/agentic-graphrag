"""Run the MCP server and copy its stdout bytes to a log file.

The stdio client reads the protocol from this process's stdout, so every byte
the server writes is forwarded unchanged. The copy in the log file lets a test
check each line of the server's stdout after the session. Usage:
``python _stdio_tee.py LOG_PATH``. The server uses the evidence corpus embedder
with the environment of this process.
"""

import subprocess
import sys
import threading

import anyio

from agrag.graphdb import build_graph_store
from agrag.mcp_server.server import build_server, serve_stdio
from agrag.mcp_server.settings import McpServerSettings
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder


_CHUNK_BYTES = 65536


def _feed_stdin(child: subprocess.Popen[bytes]) -> None:
    """Forward this process's stdin to the server until the client closes it."""
    assert child.stdin is not None
    try:
        for chunk in iter(lambda: sys.stdin.buffer.read1(_CHUNK_BYTES), b""):
            child.stdin.write(chunk)
            child.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        child.stdin.close()


def main() -> None:
    """Forward the protocol in both directions and exit with the server's code."""
    log_path = sys.argv[1]
    child = subprocess.Popen(
        [sys.executable, __file__, "--serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert child.stdout is not None
    threading.Thread(target=_feed_stdin, args=(child,), daemon=True).start()
    with open(log_path, "wb") as log:
        for chunk in iter(lambda: child.stdout.read1(_CHUNK_BYTES), b""):
            log.write(chunk)
            log.flush()
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    sys.exit(child.wait())


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve"]:
        settings = McpServerSettings()
        store = build_graph_store(settings.graph_store)
        server = build_server(store, BagOfWordsEmbedder(), settings)
        anyio.run(serve_stdio, server, store)
    else:
        main()
