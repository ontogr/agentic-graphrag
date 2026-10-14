"""Local MCP server for the evidence operations, served over stdio.

The server exposes three read-only tools: ``search_evidence``,
``fetch_evidence`` and ``check_citations``. The document scope comes only from
the server configuration, so a tool call cannot widen it. The server needs the
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
used. On the first such call the server compares the query embedder's dimension
with the stored vectors. When they differ, semantic search fails and hybrid
search returns lexical hits only.
"""
