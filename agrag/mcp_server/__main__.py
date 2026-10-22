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
from agrag.vectordb import build_vector_store


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

    store = build_graph_store(settings.graph_store)
    embedder = FastEmbedEmbedder(settings=EmbeddingSettings())
    if settings.vector_store is None:
        server = build_server(store, embedder, settings)
        anyio.run(serve_stdio, server, store)
        return

    vectors = build_vector_store(settings.vector_store)

    async def serve() -> None:
        """Keep vector client initialization and shutdown in the server loop."""
        try:
            await vectors.initialize()
            server = build_server(store, embedder, settings, vector_store=vectors)
            await serve_stdio(server, store)
        finally:
            await vectors.close()

    anyio.run(serve)


if __name__ == "__main__":
    main()
