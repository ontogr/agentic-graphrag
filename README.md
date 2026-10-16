<h1 align="center"><a href="https://github.com/ontogr/agentic-graphrag">Agentic GraphRAG</a></h1>

<div align="center">

[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ontogr/agentic-graphrag)
[![CI](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=CI&logo=githubactions)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml)
[![Integration tests](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/integration.yml?branch=main&label=integration%20tests&logo=pytest)](https://github.com/ontogr/agentic-graphrag/actions/workflows/integration.yml)
[![Codecov](https://codecov.io/gh/ontogr/agentic-graphrag/branch/main/graph/badge.svg)](https://codecov.io/gh/ontogr/agentic-graphrag)
[![PyPI](https://img.shields.io/pypi/v/agentic-graphrag.svg)](https://pypi.org/project/agentic-graphrag/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/agentic-graphrag/)
[![Downloads](https://static.pepy.tech/badge/agentic-graphrag)](https://pepy.tech/project/agentic-graphrag)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=readthedocs)](https://ontogr.github.io/agentic-graphrag/)
[![License](https://img.shields.io/github/license/ontogr/agentic-graphrag?color=green)](https://github.com/ontogr/agentic-graphrag/blob/main/LICENSE)

</div>

Agentic GraphRAG is an open source Python framework that gives AI agents a memory they can trace back to its sources.

It keeps three connected kinds of memory in one Neo4j graph: the knowledge in your documents, the tasks your agents are working on, and the decisions they have made. Add your documents and they become a knowledge graph. Agents search it, read the exact passage behind each result, and cite it. They record decisions that point to the passages they rely on, a later session picks a task up where it stopped, and a decision is flagged for review when a document behind it changes. Use it from Python, through the built-in agent, or from any MCP client.

## Table of contents

- [Installation](#installation)
- [Features](#features)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)
- [License](#license)

## Installation

Agentic GraphRAG needs Python 3.11 or newer and a Neo4j database, version 5.23 or newer. The free Neo4j Aura tier works, and so does a local Docker container.

```bash
uv pip install agentic-graphrag
```

Add the extras for the parts you use:

```bash
# Neo4j storage and local extraction
uv pip install "agentic-graphrag[neo4j,extract]"

# The built-in agent
uv pip install "agentic-graphrag[neo4j,extract,agents]"

# The MCP server
uv pip install "agentic-graphrag[neo4j,mcp]"

# PDFs and images
uv pip install "agentic-graphrag[docling]"
```

Embeddings and local extraction run on your machine, and the first run downloads the models. An LLM endpoint is optional and only the steps that need one call it, such as the built-in agent.

To build your first graph, follow the [quickstart](https://ontogr.github.io/agentic-graphrag/stable/get-started/quickstart). The [documentation](https://ontogr.github.io/agentic-graphrag/) covers the concepts, step-by-step guides, every extra, and the API reference.

## Features

### Reads the files you already have

Point it at a file, a folder, a glob pattern or plain text, and it loads what it finds. It reads PDFs, Word, PowerPoint and Excel files, Markdown, HTML, AsciiDoc, plain text, XML, logs, images, and CSV, TSV, JSON and JSON Lines data. PDFs and images need the `docling` extra. Headings, sections, tables and figures stay in the graph, and PDF pages keep their page numbers and positions. Each row of a data file and each JSON record becomes its own document, and chat exports load with one section per message. One bad file fails alone, because you choose whether to stop, skip it, or set it aside with the reason.

### Splits documents along their structure

Chunks follow headings, sections and tables instead of cutting at a fixed length. Short sections are combined so you do not end up with tiny chunks. A table stays whole when it fits, and a large table is split by rows with the header repeated in every piece. Every chunk remembers where it came from, down to its heading path and its page or character position, and the heading path goes in front of the text when the chunk is embedded. Change the chunking settings and the chunks are re-created automatically.

### Builds a knowledge graph around your own schema

Tell it which kinds of people, organizations, products or anything else matter, and which relations count. It extracts only those. You can write the schema in a few lines of Python, in a YAML or JSON file, as Pydantic classes, or import an OWL or RDFS ontology. You can also start from the default schema or a ready-made preset for legal or operations documents and extend it.

Extraction runs on your machine with GLiNER, so you can build a graph without an LLM key. You can add an LLM for the hard cases within a budget you set. Any OpenAI-compatible endpoint works, and so do many other providers, with retries and fallback between models. Anything outside your schema is saved as a candidate that you can review, approve or reject instead of losing it. Approving candidates writes a schema patch for you to look over, and your own schema file is never edited.

### Merges duplicates without losing anything

"Acme Corp" and "Acme Corporation" become one entity, and nothing is deleted to get there. It matches by exact name, by similar spelling and by meaning, and it asks an LLM about the hard pairs. When it is unsure, it does not merge. The original entities stay in the graph, and every match is a recorded link that you can inspect or undo. Preview a graph-wide merge as a dry run before you apply it, or re-check only the entities you name after a change. Conflicting property values keep the first value seen, an LLM summarizes conflicting descriptions, and entities are cleaned up when the evidence for them is removed.

### Keeps the graph current

Add the same folder again and only the documents that changed are processed. Update a document in place, and it redoes only what the change needs. If only the schema descriptions or extraction settings changed, it re-extracts without re-chunking, and a change to dates alone skips both. Delete a document from search while keeping its history, or purge it completely. Writes survive crashes, because half-finished work never shows up in search and the next start rolls back or finishes the interrupted job. You can ask for the status of any document, and every run returns a report with counts and failures for each stage.

### Finds answers and shows its sources

Every result can be traced to the exact text and document version it came from. Search by keyword, by meaning, or by both together, and get back only text the caller is allowed to read, never old versions or half-written ones. Fetch the exact text behind any result, and the text is marked when it is cut short. Citations point to a specific document version, and a citation to an older version still works and is labelled as superseded.

You can find entities and the passages that mention them, follow relations a couple of steps out, and see which relations a passage supports and which are bare graph links. You can also move from a passage to its parent section, its neighbors, or the rows around a table cell. A citation check catches sources that were never read, that belong to another document, or that are malformed. When part of a search fails or is cut short, the result says so, so an incomplete result is never mistaken for "nothing found".

### Answers broad questions with community summaries

For broad questions, Agentic GraphRAG groups related entities into communities and writes a title, summary, rating and findings for each. An LLM writes the summaries for the important communities and a simple template covers the rest, so the cost stays bounded. You can preview the groups before writing them. The summaries are searchable and are added to results when they help. Communities need the `community` extra.

### Includes an agent that researches your documents

The built-in agent searches your documents, reads passages and answers with numbered sources. It can read only the documents you give it. Every run ends with a status that says whether the agent answered, found too little evidence, returned partial results, ran out of budget, or failed to record its work. Its citations are checked against what it actually read, and it gets one chance to repair them. You cap the number of steps and tool calls in a run. It works with Anthropic, OpenAI, OpenAI-compatible and Google models, with fallback or round-robin between them.

### Remembers tasks

Give a task a name, and Agentic GraphRAG saves everything the agent says, calls and receives, in order, as the task runs. Each step is tracked as not started, in progress, completed, failed or unknown. Run the task again with the same name and it resumes, because finished steps are reused and steps that were still running are marked unknown. Retries are safe, since a repeated request returns the saved result instead of recording twice.

### Records decisions that stay tied to their evidence

A decision stores its conclusion, rationale, assumptions and open questions, along with the passages, events or other decisions it rests on. You replace or reject a decision explicitly, and the earlier version and its evidence stay. When a document that a decision cites gets a new version or is removed, the decision is flagged for review, and so are the decisions that depend on it, and no others. A decision is reaffirmed only after the current version of each cited document has been read. You can also list conflicting decisions from different tasks and search past decisions in the same project as precedents.

### Works with any MCP client

Run `agrag-mcp` to give any MCP client tools that search, read, move around documents, check citations, and manage tasks and decisions. The server runs locally and starts read-only. You choose which documents it can see and whether it can write, and a tool call cannot widen either choice. A decision can cite only evidence that the server actually read. Results have a size cap, reads have a deadline, and the server says when it left items out.

### Shows what happened

Traces for loading, extraction, LLM calls, searches and agent runs go to any OpenTelemetry backend once you pass a tracer, and nothing is recorded until then. Traces include the full text of questions, prompts and evidence, so filter them if that matters for your data. Every per-item failure carries a trace id, and dropped items are counted by reason.

### Measures quality on your own data

Score answers for correctness, faithfulness, citation accuracy, and context precision and recall. Score entity extraction, entity resolution and agent runs too, using a judge model you choose. An example script runs the answer scores on your own documents and questions.

### Fits your setup

Everything is configured with environment variables or a `.env` file. Point extraction, the agent and the judge at one OpenAI-compatible endpoint, or give each its own settings. Agentic GraphRAG refuses to send your Neo4j password over an unencrypted connection to a remote host. Install only the parts you need through extras, and tune thresholds and LLM budgets per entity and relation type.

## Project structure

```text
agrag/
├── common/data_models/   # Documents, chunks, schemas, tasks, decisions and evidence records
├── loaders/              # Core corpus readers and the Docling loaders
├── chunking/             # The section chunker
├── schema/               # Schema loading, presets and schema format export
├── candidates/           # Out-of-schema candidate capture, review and conversion
├── ingestion/            # Graph API, extraction, resolution, community detection and pipeline stages
├── embedding/            # Dense embedding interfaces
├── graphdb/              # Graph-store interface and Neo4j backend
├── cypher/               # Validated Cypher builders
├── retrieval/            # Search methods, retrievers, recipes and rerankers
├── evidence/             # Passage discovery, fetch, navigation and citation checks
├── memory/               # Tasks, events, steps and decisions
├── agents/               # The task-scoped agent, its tools and event handling
├── mcp_server/           # The agrag-mcp server
├── eval/                 # Metrics for answers, extraction, resolution and agent runs
├── llm/                  # BAML sources, generated client and provider routing
└── observability.py      # OpenTelemetry helpers

tests/
├── unit/                 # Isolated tests with external services mocked
└── integration/          # Live backend tests against Docker services
```

## Contributing

We welcome contributions of all kinds, including bug fixes, new features, documentation improvements, and more. Please read our [Contributing guide](https://github.com/ontogr/agentic-graphrag/blob/main/CONTRIBUTING.md) before submitting a pull request.

## Acknowledgements

Agentic GraphRAG builds on the amazing work done by the teams behind these papers and projects.

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
