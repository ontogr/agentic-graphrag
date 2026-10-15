"""Start the evidence MCP server on stdio."""

import importlib.util
import logging
import sys

import anyio
from pydantic import ValidationError

from agrag.embedding import EmbeddingSettings, FastEmbedEmbedder
from agrag.graphdb import build_graph_store
from agrag.mcp_server.errors import McpServerMissingExtraError
from agrag.mcp_server.settings import McpServerSettings


_EXIT_INVALID_SETTINGS = 2


def main() -> None:
    """Serve the evidence tools over stdio until the client disconnects.

    The embedding model loads on the first semantic or hybrid search, not at
    startup. This command uses FastEmbed with ``EMBEDDING_*`` settings. For other
    backends, construct the embedder and pass it to ``build_server``. The graph
    store is closed when the server stops.

    Raises:
        McpServerMissingExtraError: The ``mcp`` extra is not installed.
    """
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if importlib.util.find_spec("mcp") is None:
        raise McpServerMissingExtraError("mcp")

    from agrag.mcp_server.server import build_server, serve_stdio  # noqa: PLC0415

    try:
        settings = McpServerSettings()
    except ValidationError as exc:
        reasons = "; ".join(str(error["msg"]) for error in exc.errors())
        sys.stderr.write(f"agrag-mcp: invalid settings: {reasons}\n")
        raise SystemExit(_EXIT_INVALID_SETTINGS) from None

    store = build_graph_store("neo4j")
    embedder = FastEmbedEmbedder(settings=EmbeddingSettings())
    server = build_server(store, embedder, settings)
    anyio.run(serve_stdio, server, store)


if __name__ == "__main__":
    main()
