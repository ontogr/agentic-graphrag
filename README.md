<h1 align="center"><a href="https://github.com/ontogr/agentic-graphrag">Agentic GraphRAG</a></h1>

<h3 align="center">Build context graphs for AI agents.</h3>
<h4 align="center"><a href="https://ontogr.github.io/agentic-graphrag/latest/get-started/quickstart">Quickstart</a> | <a href="https://ontogr.github.io/agentic-graphrag/">Documentation</a> | <a href="CONTRIBUTING.md">Contributing</a></h4>


<div align="center">

[![PyPI](https://img.shields.io/pypi/v/agentic-graphrag.svg)](https://pypi.org/project/agentic-graphrag/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/agentic-graphrag/)
[![Downloads](https://static.pepy.tech/badge/agentic-graphrag)](https://pepy.tech/project/agentic-graphrag)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=readthedocs)](https://ontogr.github.io/agentic-graphrag/)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ontogr/agentic-graphrag)
[![License](https://img.shields.io/github/license/ontogr/agentic-graphrag?color=green)](https://github.com/ontogr/agentic-graphrag/blob/main/LICENSE)

</div>

<div align="center">

[![CI](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=CI&logo=githubactions)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml)
[![Integration tests](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/integration.yml?branch=main&label=integration%20tests&logo=pytest)](https://github.com/ontogr/agentic-graphrag/actions/workflows/integration.yml)
[![Codecov](https://codecov.io/gh/ontogr/agentic-graphrag/branch/main/graph/badge.svg)](https://codecov.io/gh/ontogr/agentic-graphrag)

</div>



Agentic GraphRAG is an open source Python framework that connects your documents, agent activity, and decisions in one graph. Your agents can find evidence, continue work across sessions, and revisit decisions when their sources change.

Turn documents into searchable knowledge shaped by your own schema. Give agents tools to follow relationships, read source passages, and cite what they use. Keep decisions linked to the evidence behind them. Use the Python library, connect your agent through MCP, or start with the built-in agent.

For example, a contract-review agent can record a recommendation with passages from a contract and a policy. A later session retrieves the task and its decision. When the policy changes, the decision is flagged for review against the new evidence.


## Features

### One graph for documents, tasks, and decisions

Documents, agent work, and decisions live together, so every answer can be traced back to its source.

- **Three connected layers.** The first layer holds your documents, with their sections, tables, and passages, and the people, organizations, products, and other entities found in them. The second holds named tasks, the steps agents take, and a log of what happened. The third holds the decisions agents make.
- **Every passage knows where it came from.** A passage records its document, its place in the document's structure, and the exact version it came from, with page positions for PDFs.
- **Every relation points to its evidence.** A relation between two entities links to the passages that support it, and a decision links to the text it was based on.
- **Old citations keep working.** The graph keeps the history of each document, so a citation to an older version still leads to the text that was cited.

### Build the graph around your own schema

You decide which things matter, and the graph is built around them.

- **Describe your own entities and relations.** Name the kinds of things that matter to you, such as people, contracts, or products, and the relations between them. Write the schema in code or in a configuration file, or start from a ready-made preset and extend it.
- **Extraction runs on your machine first.** You can build a graph without an LLM. When the local model is unsure about a passage, an LLM can read it, and you decide how much of each batch the LLM may read.
- **Nothing outside your schema is lost.** Anything the models find that your schema does not cover is saved for review. Approved items become part of your schema and your graph.
- **Duplicates are merged with care.** Agentic GraphRAG recognizes that "Acme Corp" and "Acme Corporation" are the same company. It starts with cheap checks and asks an LLM only about the pairs that remain unclear.
- **Every match can be undone.** A match is stored as a link between two entities, so the originals stay in the graph. You can preview a cleanup of the whole graph before you apply it.

### Search your documents and read the evidence

Agents find passages, read the exact text, and move around a document the way a person would.

- **Search by keyword, by meaning, or both.** A search returns short previews, each with an identifier for its passage. A separate step fetches the exact text.
- **You set the boundary outside the model.** You decide which documents an agent may read, and the model can only work inside that choice.
- **Source text stays findable.** Search reads the passages directly, so a passage is still found when extraction missed the fact it contains.
- **Move around a passage.** From any passage, an agent can reach the surrounding section, the neighboring passages, or the rows around a table cell, which keep their column headers.
- **Follow entities back to text.** An agent can look up an entity, see the passages that mention it, and follow its relations a few steps out. Each relation is marked as backed by a passage or as a connection without direct text.
- **Incomplete results say so.** Every result states when something was cut off or part of the search failed, so an incomplete result is never mistaken for an empty one.

### Pick up a task where it stopped

Agents can name their work, come back to it later, and keep decisions tied to the evidence behind them.

- **Resume with the full picture.** When a task resumes, the agent sees the goal, the progress so far, and the decisions already made. It reuses finished work that is still valid.
- **Interrupted work is run again.** A step that was interrupted is marked as unknown so that it can be run again. Repeating a write after a failure never records it twice.
- **Decisions carry their reasons.** A decision records a conclusion, the reasoning, the assumptions, and the open questions, along with the passages, events, or earlier decisions it relies on.
- **Source changes flag decisions.** When a document behind a decision is updated or removed, the decision is flagged for review, and so are the decisions that depend on it.
- **Reviews end in a clear action.** A reviewer can reaffirm a decision after reading the current text, or replace it with a new one that explains the change. The earlier version stays in the history.
- **Past decisions work as precedent.** Agents can search earlier decisions in the same project.

### Use the built-in agent or any MCP client

Use the agent that ships with the library, or connect your own through MCP.

- **Answers cite numbered sources.** The built-in agent searches your documents, reads passages, and answers with numbered sources.
- **Every citation is checked.** The passage must have been read during that run, it must belong to the documents the agent may use, and it must match the version cited. If a citation fails the check, the agent gets one chance to fix it.
- **Every run ends with a status.** The status tells you whether the agent answered, found too little evidence, or reached a limit. You set how many steps and tool calls a run may use.
- **Choose your model.** Use Anthropic, OpenAI, Google, or any OpenAI-compatible model, with fallback between them.
- **The same tools work through MCP.** A local MCP server gives other agents the same tools. It starts read-only and shows only the documents you choose, and you decide whether a client may record tasks and decisions.
- **Trace and evaluate your runs.** Runs can be traced with OpenTelemetry, and the evaluation tools score answers, citations, and agent runs on your own questions.

The [full feature list](https://ontogr.github.io/agentic-graphrag/latest/get-started/features) covers the rest.

## Quickstart

Install graph storage, local extraction, and the built-in agent. This example uses the current `main` APIs:

```bash
uv pip install "agentic-graphrag[neo4j,extract,agents] @ git+https://github.com/ontogr/agentic-graphrag.git@main" --torch-backend=auto
```

You need Python 3.11+, a configured Neo4j database, and an LLM endpoint. The [setup guide](https://ontogr.github.io/agentic-graphrag/latest/get-started/quickstart) covers database and model configuration.

<details>
<summary>Connection settings</summary>

Set these variables in your environment or an existing `.env` file. Replace the database credentials and agent values with your own. Do not commit credentials.

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=agrag-quickstart
NEO4J_DATABASE=neo4j
AGENT_LLM_BASE_URL=https://your-endpoint.example.com/v1
AGENT_LLM_API_KEY=your-api-key
AGENT_LLM_MODEL_ID=your-model-id
```

For a remote Neo4j instance, use its credentials and an encrypted URI such as `neo4j+s://`. The agent sends questions and retrieved evidence to the configured model endpoint.

</details>

Point the library at an existing document, then ask a question. Run this in an async function or a notebook that supports `await`:

```python
from pathlib import Path

from agrag.agents import AgentLLMSettings, build_agent
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import ExtractionSettings, Graph


document = Path("your-document.md").resolve()
store = build_graph_store("neo4j")
embedder = build_embedder("ibm-granite/granite-embedding-small-english-r2")

try:
    graph = await Graph.open(
        schema="operations",
        graph_store=store,
        embedder=embedder,
        extraction_settings=ExtractionSettings(mode="gliner"),
        max_llm_pairs=0,
    )
    await graph.add(document)

    agent = build_agent(
        graph_store=store,
        embedder=embedder,
        scope=frozenset({str(document)}),
        project_id="my-project",
        agent_id="researcher",
        llm_settings=AgentLLMSettings.from_openai_compatible_env(),
    )
    result = await agent.ainvoke({
        "task_name": "document-review",
        "question": "What does this document require? Cite your sources.",
    })
    print(result["answer"])
finally:
    await store.close()
```

Reuse the project and task name to continue from recorded progress. For explicit decisions and source-change review, see the [connected-memory guide](https://ontogr.github.io/agentic-graphrag/latest/guides/connected-memory/). It records a decision, changes a source document, and reviews the decision.

## Use MCP

Install the `neo4j,mcp` extras from the same source revision as your ingestion code, then configure `agrag-mcp` as a local stdio server in your MCP client. Use the same embedding model as ingestion for semantic search. See the [MCP server guide](https://ontogr.github.io/agentic-graphrag/latest/guides/run-the-mcp-server).

The server starts read-only. Configure the permitted document keys, and enable task and decision writes only for trusted clients. Document scope controls evidence retrieval; it does not provide authentication or per-user authorization for memory records.

## Contributing

We welcome bug fixes, new features, documentation improvements, and other contributions. Please read our [Contributing guide](CONTRIBUTING.md) before submitting a pull request.

## Acknowledgements

Agentic GraphRAG builds on the work behind these papers and projects.

- [Microsoft GraphRAG](https://arxiv.org/abs/2404.16130) for hierarchical communities and community reports
- [Graphiti](https://github.com/getzep/graphiti) for layered graph search and entity-aware retrieval
- [Cognee](https://github.com/topoteretes/cognee) for data pipelines, graph memory, and consolidation
- [KG-Gen](https://github.com/stair-lab/kg-gen) for knowledge-graph extraction and alias deduplication
- [FalkorDB GraphRAG SDK](https://github.com/FalkorDB/GraphRAG-SDK) for graph-native retrieval and entity resolution
- [Neo4j GraphRAG](https://github.com/neo4j/neo4j-graphrag-python) for Neo4j retrieval and vector integration
- [LightRAG](https://github.com/HKUDS/LightRAG) for graph and vector retrieval
- [PathRAG](https://github.com/BUPT-GAMMA/PathRAG) for relational-path retrieval
- [GLiNER](https://arxiv.org/abs/2311.08526) for generalist zero-shot information extraction
- [BAML](https://boundaryml.com/), [Docling](https://github.com/docling-project/docling), and [Chonkie](https://github.com/chonkie-inc/chonkie) for typed LLM calls, document parsing, and chunk splitting

## License

Agentic GraphRAG is licensed under the [Apache License 2.0](https://github.com/ontogr/agentic-graphrag/blob/main/LICENSE).
