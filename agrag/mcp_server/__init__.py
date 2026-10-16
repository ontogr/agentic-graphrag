"""Local MCP server for the evidence operations, served over stdio.

The server exposes bounded evidence discovery, navigation and citation tools.
With ``AGRAG_MCP_PROJECT_ID`` and ``AGRAG_MCP_AGENT_ID`` set it also exposes
project-scoped task and decision reads. Writes need
``AGRAG_MCP_READ_ONLY=false`` and both ids; the server starts read-only by
default. Decision rejection also needs ``AGRAG_MCP_ALLOW_REJECT=true``. The
document scope comes only from server configuration, so a tool call cannot
widen it. The server needs the
``mcp`` and ``neo4j`` extras. Install them with ``uv sync --extra mcp --extra
neo4j``.

A client starts the server with a configuration entry such as this one:

.. code-block:: json

    {
      "mcpServers": {
        "agrag-evidence": {
          "command": "uv",
          "args": ["run", "--extra", "mcp", "--extra", "neo4j", "agrag-mcp"],
          "env": {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "<password>",
            "AGRAG_MCP_SCOPE_DOCUMENT_KEYS": "privacy_qa/Keep.txt"
          }
        }
      }
    }

``AGRAG_MCP_SCOPE_DOCUMENT_KEYS`` takes a comma-separated list of document
keys. The server refuses to start when the list is empty. Logs go to stderr,
and stdout carries only protocol messages.

Semantic and hybrid search need the same ``EMBEDDING_*`` settings that ingestion
used. Each such call compares the query embedder's dimension with the vector
index. When dimensions differ, semantic search fails and hybrid search returns
lexical hits only. Equal dimensions do not verify model identity. The command
uses FastEmbed. To use another backend, pass its embedder to ``build_server``.
"""
