---
title: Core API
sidebar_position: 1
sidebar_class_name: agrag-hidden
---

# Core API

This page lists the objects that most programs use. Each row gives the import line and links to the full reference for that package.

The top-level `agrag` package exports nothing. Import each name from the package in the table.

## Entry points

| Object | Import | Role |
| --- | --- | --- |
| `Graph` | `from agrag.ingestion import Graph` | Opens a graph. Adds, updates, and deletes documents. Consolidates duplicates and detects communities. See [agrag.ingestion](ingestion/index.md). |
| `GraphSchema`, `GENERIC` | `from agrag.common.data_models import GENERIC, GraphSchema` | The entity types, relation types, and valid patterns of a graph. `GENERIC` is a preset with five entity types. See [agrag.common](common/index.md). |
| `Neo4jGraphStore` | `from agrag.graphdb import Neo4jGraphStore, build_graph_store` | The graph store. It reads the `NEO4J_*` settings. See [agrag.graphdb](graphdb/index.md). |
| Vector stores | `from agrag.vectordb import QdrantVectorStore, WeaviateVectorStore, MilvusVectorStore, build_vector_store` | Optional dedicated vector stores for dense and hybrid search. See [agrag.vectordb](vectordb/index.md). |
| `build_embedder` | `from agrag.embedding import build_embedder` | Builds a dense embedder from a model name. See [agrag.embedding](embedding/index.md). |
| Extractors | `from agrag.ingestion import GlinerExtractor, BAMLExtractor, EscalatingExtractor` | Read one chunk and return entities and relations. GLiNER runs locally. BAML calls an LLM. The escalating extractor runs GLiNER first and calls the LLM for weak chunks. |
| `ErrorPolicy` | `from agrag.loaders import ErrorPolicy` | The action for a source that fails: `RAISE`, `SKIP`, or `QUARANTINE`. See [agrag.loaders](loaders/index.md). |
| `SearchEngine`, `RetrievalSettings` | `from agrag.retrieval import SearchEngine, RetrievalSettings` | Runs retrieval recipes over the graph. See [agrag.retrieval](retrieval/index.md). |
| `build_agent` | `from agrag.agents import build_agent` | Builds the planner, researcher, and verifier agent. Accessing it needs the `agents` extra. See [agrag.agents](agents/index.md). |
| `get_tracer` | `from agrag.observability import get_tracer` | Returns the tracer you pass, or a no-op tracer. See [agrag.observability](observability/index.md). |

## Tracing

Every component takes an OpenTelemetry `Tracer` in a `tracer=` argument. When you pass `None`, the component records no spans.

## Results and settings

| Object | Import | Role |
| --- | --- | --- |
| `AddResult` | `from agrag.ingestion import AddResult` | The counts and failures that `Graph.add` returns. |
| `AgentRunResult` | `from agrag.agents import AgentRunResult` | The messages and the citation ledger that an agent run returns. |
| `Ledger` | `from agrag.agents import Ledger` | Maps citation keys such as `E1` and `C3` to the evidence behind them. |
| `AgentLLMSettings` | `from agrag.agents import AgentLLMSettings` | The LLM clients that the agent uses. |
| `SearchFilters` | `from agrag.retrieval import SearchFilters` | Limits a search to labels, documents, or properties. |

Environment variables for every configuration class are in the [Configuration reference](../reference/configuration.mdx).

## Other packages

- [agrag.chunking](chunking/index.md): the chunkers, `Chunking` rules, and the default preset.
- [agrag.eval](eval/index.md): metrics that score answers, retrieval, and agent runs. Needs the `eval` extra.

## Related

- Tutorial: [Quickstart](../get-started/quickstart.mdx).
- How-to: [Ingest documents](../guides/ingest-documents.mdx), [Retrieve and answer](../guides/retrieve-and-answer.mdx).
- Explanation: [Architecture](../concepts/architecture.mdx).
