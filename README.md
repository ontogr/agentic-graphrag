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

### Build a graph around your domain

Define the people, organizations, products, and relationships that matter to your application. Extract them with local GLiNER models, add an LLM for harder cases, and review candidates outside your schema. Connect matching entities without discarding the originals, using a schema from Python, YAML, JSON, Pydantic models, or an OWL or RDFS ontology.

### Search the graph. Read the evidence.

Search source passages by keyword, meaning, or both. Follow entity relationships and move between passages and surrounding sections. Direct passage search keeps source text accessible even when extraction misses a fact.

### Cite a specific source version

Fetch the text behind a result and cite the document version it came from. The built-in agent checks references against fetched evidence and renders valid citations as numbered sources. These checks establish where the evidence came from, not whether it proves a conclusion; retained older passages are marked as superseded after an update.

### Continue work across sessions

Save task progress, messages, tool results, and decisions. Resume a named task from its recorded state and fetch supporting history when needed. The built-in agent captures messages and tool outcomes automatically; external MCP clients record them through explicit tools.

### Revisit decisions when evidence changes

Record decisions with their rationale, assumptions, and supporting evidence. Source updates flag dependent decisions for review, including decisions linked through explicit dependencies. Reaffirm or replace a decision explicitly while preserving its history.

### Use your own agent, or start with ours

Use the same evidence and task operations from Python or through the local MCP server. The built-in agent combines document research, task recording, and numbered citations, with limits on steps and tool calls. Choose Anthropic, OpenAI, OpenAI-compatible, or Google models, with fallback or round-robin routing.

### Also included

- Read prose, office documents, structured records, and chat exports. Section-aware chunking preserves heading paths and table context; PDF and image loading needs the `docling` extra.
- Generate community summaries with the `community` extra and use them through the retrieval API. Community retrieval is separate from the built-in agent's evidence tools.
- Pass an OpenTelemetry tracer to inspect supported operations, and use evaluation tools with your own data and judge model. Traces can contain full prompts, questions, and evidence, so review your telemetry handling before enabling them.
- Run embeddings and GLiNER extraction locally, or configure LLM-backed roles separately. Settings use environment variables and `.env` files where supported; schemas, document scope, and component choices can also be supplied in Python.

## Quickstart

Install graph storage, local extraction, and the built-in agent. This example uses the current `main` APIs:

```bash
uv pip install "agentic-graphrag[neo4j,extract,agents] @ git+https://github.com/ontogr/agentic-graphrag.git@main" --torch-backend=auto
```

You need Python 3.11+, a configured Neo4j database, and an LLM endpoint. The [setup guide](https://ontogr.github.io/agentic-graphrag/latest/get-started/quickstart) covers database and model configuration. Local models download on first use; the agent sends retrieved evidence to your chosen LLM.

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

Reuse the project and task name to continue from recorded progress. For explicit decisions and source-change review, see the [connected workflow example](docs/docs/guides/connected-memory.mdx), which runs from a repository checkout with its fixture dependencies.

## Use MCP

Install the `neo4j,mcp` extras from the same source revision as your ingestion code, then configure `agrag-mcp` as a local stdio server in your MCP client. Use the same embedding model as ingestion for semantic search. See the [MCP configuration reference](agrag/mcp_server/settings.py) and the [MCP client in the connected-memory example](examples/connected_memory/workflow.py).

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
