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
| `GraphSchema`, `DEFAULT_SCHEMA`, `OPERATIONS`, `LEGAL` | `from agrag.common.data_models import DEFAULT_SCHEMA, GraphSchema, LEGAL, OPERATIONS` | The entity types, relation types, and valid patterns of a graph. `DEFAULT_SCHEMA` has nine entity types and eight relation types. `OPERATIONS` and `LEGAL` add entity types to it. See [agrag.common](common/index.md). |
| `Neo4jGraphStore` | `from agrag.graphdb import Neo4jGraphStore, build_graph_store` | The graph store. It reads the `NEO4J_*` settings. See [agrag.graphdb](graphdb/index.md). |
| `build_embedder` | `from agrag.embedding import build_embedder` | Builds a dense embedder from a model name. See [agrag.embedding](embedding/index.md). |
| Extractors | `from agrag.ingestion import GlinerExtractor, BAMLExtractor` | Read one chunk and return entities and relations. GLiNER runs locally. BAML calls an LLM. `Graph` selects extractors by mode and can build an LLM extractor from environment settings. See [Choose an extraction mode](../guides/choose-an-extraction-mode.mdx). |
| `ErrorPolicy` | `from agrag.loaders import ErrorPolicy` | The action for a source that fails: `RAISE`, `SKIP`, or `QUARANTINE`. See [agrag.loaders](loaders/index.md). |
| `SearchEngine`, `RetrievalSettings` | `from agrag.retrieval import SearchEngine, RetrievalSettings` | Runs retrieval recipes over the graph. See [agrag.retrieval](retrieval/index.md). |
| Evidence functions | `from agrag.evidence import discover, fetch, navigate, find_entities, explore, check_citations, render_citations, source_status` | Find passages, fetch the exact text behind an evidence id, move between passages, find entities, and check citations. `source_status` reports a document's current, pending, failed, deleted, or unknown state. See [agrag.evidence](evidence/index.md). |
| `TaskMemory`, `DecisionMemory` | `from agrag.memory import TaskMemory, DecisionMemory` | Record task events and steps, and record, replace, review, and search decisions. See [agrag.memory](memory/index.md). |
| `build_agent` | `from agrag.agents import build_agent` | Builds the task-scoped evidence agent. Accessing it needs the `agents` extra. See [agrag.agents](agents/index.md). |
| `get_tracer` | `from agrag.observability import get_tracer` | Returns the tracer you pass, or a no-op tracer. See [agrag.observability](observability/index.md). |

## Tracing

Every component takes an OpenTelemetry `Tracer` in a `tracer=` argument. When you pass `None`, the component records no spans.

## Results and settings

| Object | Import | Role |
| --- | --- | --- |
| `AddResult` | `from agrag.ingestion import AddResult` | The counts and failures that `Graph.add` returns. |
| `AgentRunResult` | `from agrag.agents import AgentRunResult` | What an agent run returns: the answer with numbered sources, the status, the validated citations, the invalid citations, any recording failures, the task name with its last event number, and the messages. |
| `AgentLLMSettings` | `from agrag.agents import AgentLLMSettings` | The LLM clients that the agent uses. |
| `SearchFilters` | `from agrag.retrieval import SearchFilters` | Limits a search to labels, documents, or properties. |

Environment variables for every settings class are in the [Configuration reference](../reference/configuration.mdx).

## Other packages

- [agrag.candidates](candidates/index.md): list, approve, reject, and prune extraction candidates, and write schema patches.
- [agrag.chunking](chunking/index.md): the chunkers, `Chunking` rules, and the default preset.
- [agrag.eval](eval/index.md): metrics that score answers, retrieval, and agent runs. Needs the `eval` extra.

## Related

- Tutorial: [Quickstart](../get-started/quickstart.mdx).
- How-to: [Ingest documents](../guides/ingest-documents.mdx), [Retrieve and answer](../guides/retrieve-and-answer.mdx).
- Explanation: [Architecture](../concepts/architecture.mdx).
