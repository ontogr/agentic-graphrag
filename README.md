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
[![License](https://img.shields.io/github/license/ontogr/agentic-graphrag?color=green)](LICENSE)

[Documentation](https://ontogr.github.io/agentic-graphrag/) | [Quickstart](#quickstart) | [Features](#features) | [Concepts](https://ontogr.github.io/agentic-graphrag/stable/concepts/architecture) | [Guides](https://ontogr.github.io/agentic-graphrag/stable/guides/ingest-documents) | [API reference](https://ontogr.github.io/agentic-graphrag/stable/api)

</div>

Agentic GraphRAG keeps what an agent knows, what it is working on, and what it has decided in one Neo4j graph. The graph holds your documents with their sections, tables, entities and relations. It also holds named tasks with an event log, and decision records that cite the exact passages they rest on.

An agent, or any MCP client, can search the documents, fetch the exact text of a passage, and cite it. It can then record a decision with that passage as support, and a later session can resume the task by name. When a cited document gets a new version, the decisions that cite it are flagged for review, and the agent must fetch the current text before it reaffirms them.

## Three connected layers

The graph has three layers, and explicit references connect them.

| Layer | What it holds | What you can do with it |
| --- | --- | --- |
| Knowledge | Documents, sections, tables, chunks, entities, relations and communities, all with their source versions | Add and update documents, search them, fetch the exact text behind a result, and cite it |
| Working | Named tasks, each with a goal, an append-only event log and named steps | Resume a task by name from a bounded view, and rerun only the steps that did not finish |
| Decision | Decisions with a conclusion, rationale, assumptions, open questions and typed support | Supersede, reject or reaffirm a decision, and review it when a cited document changes |

## Ways to use it

- The Python library. `Graph` builds and updates the knowledge layer. `agrag.evidence` finds, fetches and navigates passages. `agrag.memory` stores tasks and decisions.
- The built-in agent. `build_agent` returns one task-scoped agent that searches, cites, records its events and returns a status with its answer.
- The MCP server. `agrag-mcp` serves the same evidence, task and decision operations to any MCP client over stdio.

## Installation

Agentic GraphRAG requires Python 3.11 or newer and a Neo4j database, version 5.23 or newer.

```bash
uv pip install agentic-graphrag
```

Install only the integrations you use:

```bash
# Neo4j storage and local extraction
uv pip install "agentic-graphrag[neo4j,extract]"

# The built-in agent
uv pip install "agentic-graphrag[neo4j,extract,agents]"

# The MCP server
uv pip install "agentic-graphrag[neo4j,mcp]"

# PDF and image files
uv pip install "agentic-graphrag[docling]"

# LLM extraction, resolution checks and community reports
uv pip install "agentic-graphrag[llm]"
```

| Extra | Adds |
| --- | --- |
| `neo4j` | Neo4j graph storage and native vector and full-text search |
| `extract` | Local GLiNER 2.5 extraction |
| `llm` | BAML-powered extraction, match verification and community reports |
| `agents` | The LangGraph and DeepAgents runtime for the built-in agent |
| `mcp` | The `agrag-mcp` server |
| `docling` | The layout and table models for PDF and image files |
| `embed-local` | Sentence Transformers, for embedding models that the default embedder does not support |
| `community` | Leiden community detection |
| `schema-formats` | OWL and RDFS Turtle schema import |
| `observability` | OpenTelemetry SDK, OTLP export and OpenInference instrumentation |
| `eval` | The DeepEval and AgentEvals metrics in `agrag.eval` |

## What runs where

- Neo4j stores the graph and its vector and full-text indexes. The free [Neo4j Aura](https://ontogr.github.io/agentic-graphrag/stable/get-started/quickstart) tier works, and so does a local Docker container.
- Embeddings (FastEmbed) and GLiNER extraction run on your machine. The first run downloads the models, which is about 850 MB in total.
- An LLM endpoint is optional. The built-in agent, LLM extraction, the LLM tier of entity resolution, community reports and the evaluation judge call one. The endpoint receives the text of the chunks, questions or passages that the step reads.
- The MCP server runs locally over stdio. It reads only the document keys that you set in its environment.
- Traces include the full text of questions, prompts and evidence. Filter them in a span processor if that matters for your data.

## Quickstart

The quickstart builds a small graph from two documents, asks a question that needs both, and shows the saved task. Save your Neo4j credentials as `.env` in the working directory. The file sets `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`. The [full quickstart](https://ontogr.github.io/agentic-graphrag/stable/get-started/quickstart) shows the Aura setup.

```bash
uv venv
source .venv/bin/activate
uv pip install "agentic-graphrag[neo4j,extract,agents]" --torch-backend=auto
```

### Build a graph

Save this script as `build_graph.py`. It needs no LLM key, and it writes the two documents to a `corpus` folder. The example passes `GlinerExtractor` directly, so GLiNER always runs. To prevent extraction LLM use when an extraction LLM is configured, set `EXTRACTION_MODE=gliner` in `.env` or the shell.

```python
import asyncio
from pathlib import Path

from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import GlinerExtractor, Graph

CORPUS = Path("corpus")
FILES = {
    "people.txt": "Mara Ellison works at Brightwell Robotics.",
    "companies.txt": (
        "Tomas Reyes founded Brightwell Robotics. "
        "Brightwell Robotics is headquartered in Tallinn."
    ),
}
SCHEMA = {
    "name": "company-facts",
    "entities": [
        {"label": "Person", "description": "A named individual."},
        {"label": "Organization", "description": "A company or institution."},
        {"label": "Location", "description": "A city or country."},
    ],
    "relations": [
        "Person-FOUNDED->Organization",
        "Person-WORKS_AT->Organization",
        "Organization-HEADQUARTERED_IN->Location",
    ],
}


async def main() -> None:
    CORPUS.mkdir(exist_ok=True)
    for name, text in FILES.items():
        path = CORPUS / name
        if not path.exists():
            path.write_text(text + "\n", encoding="utf-8")

    graph_store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=SCHEMA,
        graph_store=graph_store,
        embedder=build_embedder("ibm-granite/granite-embedding-small-english-r2"),
        extractor=GlinerExtractor(),
    )
    try:
        result = await graph.add(source=CORPUS)
        print("documents:", result.ingestion.documents)
        print("entities extracted:", result.extraction.entities_extracted)
        print("relations extracted:", result.extraction.relations_extracted)
    finally:
        await graph_store.close()


if __name__ == "__main__":
    asyncio.run(main())
```

```bash
python build_graph.py
```

### Ask a question

The agent needs an OpenAI-compatible LLM endpoint. Add `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` to `.env`. Then save this script as `ask.py`. A document added from a file has the absolute path of the file as its key, and the agent reads only the keys in its scope.

```python
import asyncio
from pathlib import Path

from agrag.agents import AgentLLMSettings, build_agent
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store

QUESTION = "Who founded the company that Mara Ellison works at?"
SCOPE = frozenset(str(path.resolve()) for path in Path("corpus").glob("*.txt"))


async def main() -> None:
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        agent = build_agent(
            graph_store=graph_store,
            embedder=build_embedder("ibm-granite/granite-embedding-small-english-r2"),
            scope=SCOPE,
            project_id="quickstart",
            agent_id="quickstart-agent",
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
        )
        result = await agent.ainvoke(
            {"task_name": "company-founder", "question": QUESTION}
        )
        print(result["status"])
        print(result["answer"])
        for item in result["citations"]:
            print(item.evidence_id)
    finally:
        await graph_store.close()


asyncio.run(main())
```

```bash
BAML_LOG=off python ask.py
```

The wording of the answer varies with your model. A run prints the status, the answer, and the evidence ids of the passages that the agent fetched and cited.

```text
answered
Tomas Reyes founded Brightwell Robotics, where Mara Ellison works.
ev_...
```

The question needs a fact from each document. The agent finds both passages, fetches their text, and cites them. The run is saved as the task `company-founder`, and running `ask.py` again with the same task name resumes that task.

### Look at the saved task

The task, its events and any decisions are stored in the graph. Save this script as `inspect_task.py` to read them.

```python
import asyncio

from agrag.graphdb import build_graph_store
from agrag.memory import DecisionMemory, TaskMemory


async def main() -> None:
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        ids = {"project_id": "quickstart", "agent_id": "quickstart-agent"}
        tasks = TaskMemory(graph_store, **ids)
        decisions = DecisionMemory(graph_store, **ids)
        print(await tasks.get_task("company-founder"))
        print(await decisions.list_review(task_name="company-founder"))
    finally:
        await graph_store.close()


asyncio.run(main())
```

### Change a document

Edit `corpus/companies.txt` and run `build_graph.py` again. `Graph.add` skips documents whose content is unchanged and replaces the changed document with a new version. Every active decision that cites the old version is then flagged, and `list_review` returns it. The agent must fetch the current text and reaffirm or supersede the decision before it relies on it.

### Serve the graph to an MCP client

Install the `mcp` extra, then point an MCP client at the `agrag-mcp` command. The server reads only the document keys in `AGRAG_MCP_SCOPE_DOCUMENT_KEYS`, which is a comma-separated list. No tool argument can widen that scope.

```json
{
  "mcpServers": {
    "agrag": {
      "command": "agrag-mcp",
      "env": {
        "NEO4J_URI": "neo4j+s://<your-instance>.databases.neo4j.io",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "<your-password>",
        "AGRAG_MCP_SCOPE_DOCUMENT_KEYS": "/path/to/corpus/people.txt,/path/to/corpus/companies.txt"
      }
    }
  }
}
```

The server starts read-only. It then offers the evidence tools `search_evidence`, `fetch_evidence`, `check_citations`, `find_entities`, `explore` and `navigate`. With `AGRAG_MCP_PROJECT_ID` and `AGRAG_MCP_AGENT_ID` set, it adds read tools for tasks and decisions, such as `get_task`, `list_events`, `search_decisions` and `list_needing_review`. Set `AGRAG_MCP_READ_ONLY=false` to add the write tools `create_task`, `record_event`, `set_step`, `record_decision`, `supersede_decision`, `reaffirm_decision` and `continue_review_propagation`. Set `AGRAG_MCP_ALLOW_REJECT=true` to add `reject_decision`.

## Features

The lists below describe what the library does today. Each group links to the matching documentation.

### Loading documents

- `Graph.add` accepts a file, a directory, a glob, a list of paths, a raw string, or prebuilt `Document` objects.
- Core readers handle plain text, log and XML files, and each paragraph keeps its character span in the document text.
- Docling parses Markdown, HTML, AsciiDoc, Word, PowerPoint and Excel files into sections, tables and figures with no extra install.
- Docling parses PDF and image files, with OCR chosen per file, and both formats need the `docling` extra.
- CSV, TSV, JSON and JSON Lines files produce one document per row, record or array element, with an optional id column.
- Each file goes to one loader by its extension, and a format whose extra is missing is reported with the extra to install.
- Each source can raise, skip or quarantine on error, so one bad file does not have to stop a batch.
- A document key comes from the absolute path plus any record id or index, so adding a changed file updates the stored document.
- Text is decoded with encoding detection, a byte-order mark is removed, line endings become LF, and NFKC normalization is on by default.
- Sources over 32 MiB are rejected by default, and `ReadOptions.max_document_bytes` sets the limit.
- A chat loader reads a conversation file with one section per message when you pass it for a single file.
- Docling headings set the section depth, using PDF bookmarks or dotted heading numbers.

Read more: [loading](https://ontogr.github.io/agentic-graphrag/stable/concepts/loading) and [ingest documents](https://ontogr.github.io/agentic-graphrag/stable/guides/ingest-documents).

### Chunking

- One section-aware chunker packs the sections of each document into chunks of up to 600 tokens by default, in reading order.
- A table stays whole when it fits. A larger table is split into row groups that each repeat the header row.
- Table rows and running text never share a chunk.
- A chunk that ends small is carried into the next section, so short sections do not each make a tiny chunk.
- A single unit over the size limit is split with the Chonkie recursive splitter, and every piece is checked against the source text.
- Each chunk records its heading path, the sections it covers, and the graph node it hangs under.
- Chunks record character offsets for text sources, and page numbers with bounding boxes for layout sources.
- Each chunk carries the chunker name and a fingerprint of its settings, and a document is re-chunked when those settings change.
- A chunk id is derived from the document, its version, the chunker fingerprint and the chunk index.
- Consecutive chunks of a document are linked with `NEXT_CHUNK` edges.
- Record sources make one chunk per row, unless the row is over the size limit.
- A chat file loaded with the chat loader packs consecutive messages into shared windows.
- Each chunk can be embedded with its heading path in front of its text.

Read more: [chunking](https://ontogr.github.io/agentic-graphrag/stable/concepts/chunking) and [configure chunking](https://ontogr.github.io/agentic-graphrag/stable/guides/configure-chunking).

### Schemas, extraction and candidates

- A schema can be a dict, a list of labels and `Source-LABEL->Target` triples, a YAML or JSON file, Pydantic classes, or an OWL/RDFS Turtle file. Each form loads into the same validated schema object.
- A schema can extend the built-in default schema or a shipped preset, with explicit overrides, exclusions and added relation patterns.
- The default schema has nine entity types and eight relation types, and each relation has its allowed source and target pairs.
- The `operations` and `legal` presets add entity types to the default schema.
- A local GLiNER model extracts entities and relations from each chunk without an LLM key.
- A relation from the local model is kept only when its score is at least 0.7 and its endpoint types match an allowed pair in the schema.
- In `hybrid` mode, the weakest chunks go to an LLM, limited to a configurable share of each batch.
- Chunks with a kept entity whose type declares properties also go to the LLM, because only the LLM fills property values.
- LLM calls go through BAML with eight supported providers, with retry, and with fallback or round-robin across several configured clients.
- Extraction items that the schema does not allow are stored as `Candidate` nodes linked to their source chunks, not dropped.
- Candidates can be listed, searched, approved and rejected. Approved candidates convert into entities, relations or properties after the schema patch is applied.
- Approving candidates writes a schema patch file for review, and Agentic GraphRAG never edits your schema file.
- A schema can be exported to JSON Schema, SHACL or JSON-LD with Python functions.

Read more: [extraction](https://ontogr.github.io/agentic-graphrag/stable/concepts/extraction), [define a graph schema](https://ontogr.github.io/agentic-graphrag/stable/guides/define-a-graph-schema), [choose an extraction mode](https://ontogr.github.io/agentic-graphrag/stable/guides/choose-an-extraction-mode) and [review candidates](https://ontogr.github.io/agentic-graphrag/stable/guides/review-candidates).

### Entity resolution

- Mentions with the same label and the same normalized text share one entity node, which records how many mentions and which source chunks it received.
- Fuzzy, embedding and LLM matches are stored as `MATCHES` edges, so the raw entities and their relations stay in the graph unchanged.
- Each connected set of matched entities gets one derived `ResolvedEntity` node, linked to its members by `RESOLVED_AS` edges.
- A pair that no tier can decide, such as one whose LLM request failed, is left unmatched and is never treated as a rejection.
- Ambiguous pairs go to the LLM in batches, most similar first, capped at 500 pairs per label by default through `max_llm_pairs`.
- `Graph.consolidate()` runs resolution over every stored entity. It is a dry run by default, and with `apply=True` it writes the matches it finds.
- `Graph.reevaluate(entity_ids)` checks matches among the entities you name. It adds newly confirmed matches and deactivates an edge only when current evidence rejects its pair.
- `Graph.deactivate_match(match_id)` deactivates one match edge and rebuilds the affected resolved entities, leaving the raw entities in place.
- When two entities conflict on a property, the first value seen is kept. Conflicting descriptions are summarized by an LLM, with a plain join as the fallback.
- Each resolved entity's embedding has a sync status, and search returns only resolved entities whose embedding is synced.
- After an ingest job commits, the entities it created are resolved against everything already committed. Concurrent ingests that name one thing differently still end up in one cluster.
- When a document update, delete or purge leaves an entity with no remaining evidence, that entity and its match edges are removed.
- The LLM tier reads its settings from the `EXTRACTION_LLM_*` variables or from `LLM_BASE_URL` and `LLM_MODEL_ID`. Without them, its pairs stay undecided.

Read more: [resolution](https://ontogr.github.io/agentic-graphrag/stable/concepts/resolution), [resolved entities](https://ontogr.github.io/agentic-graphrag/stable/concepts/resolved-entities) and [consolidate duplicates](https://ontogr.github.io/agentic-graphrag/stable/guides/consolidate-duplicates).

### Graph storage and embeddings

- The graph and its vectors live in one Neo4j database, reached through one Bolt connection to Aura or to a local server.
- Nodes and relationships are written in batches, and each failed record is reported by id, so one bad row does not fail its batch.
- Uniqueness constraints cover node ids, merge keys and relationship ids, and Neo4j native vector and full-text indexes are created for you.
- A graph whose embedder dimension does not match an existing vector index is refused when it opens.
- Search runs on each label's native vector index, filters results by node properties, and widens the search when a filter removes hits.
- FastEmbed embeds text on the CPU by default, using the Granite model unless `EMBEDDING_MODEL` names another.
- Sentence Transformers embeds text when the `embed-local` extra is installed and you build the embedder explicitly.
- Model loads and encoding run in worker threads, so the event loop stays free during a slow embed.
- Node identity stays stable when labels change, and labels are merged instead of replaced.
- Rows written by an in-flight job stay out of search results until the job commits.
- A plaintext `bolt://` or `neo4j://` URI to a non-local host is rejected when settings are built.
- All Neo4j connection settings come from `NEO4J_*` variables, and all embedder settings come from `EMBEDDING_*` variables.

Read more: [graph storage](https://ontogr.github.io/agentic-graphrag/stable/concepts/graph-storage).

### Adding, updating and deleting documents

- Calling `Graph.add()` again skips documents whose content is unchanged and replaces the current version of documents whose content changed.
- `Graph.update()` replaces a document by key, and the old version's links close when the new version commits.
- `Graph.update()` re-extracts entities in place when only extraction settings or descriptions change, and keeps the chunks and their embeddings.
- `Graph.update()` writes only the publication and content dates when only those change, without chunking or extraction.
- `Graph.delete_document()` removes a document from search when the call commits, and keeps its nodes and history.
- `Graph.purge_document()` hard-deletes the chunks, sections, tables and figures of every version, along with the relation and candidate evidence that cites them.
- Each write runs as a per-document job with a lease that lasts 60 seconds by default, and `Graph.open()` rolls back or finishes a job that a crash left behind.
- Writes from a running job stay hidden from search until the job commits.
- A chunk whose extraction failed is marked, so the next update extracts it again instead of skipping the document.
- `AddResult` reports counts for each pipeline stage, and each stage keeps up to 200 failure records along with the true total.
- `on_progress` receives a partial `AddResult` after each batch of up to 100 documents.
- `Graph.source_status()` reports whether a key is current, pending, failed, deleted or unknown, with its job lease and the readiness of the chunk search indexes.

Read more: [update and delete documents](https://ontogr.github.io/agentic-graphrag/stable/guides/update-and-delete-documents) and [ingestion](https://ontogr.github.io/agentic-graphrag/stable/concepts/ingestion).

### Communities

- `Graph.detect_communities()` groups the entity graph with Leiden clustering. It shows the groups without writing them unless you pass `apply=True`.
- Each relation is weighted by the number of source chunks that support it, so an unsupported relation adds nothing to a community's importance.
- Communities above an internal weight threshold get an LLM-written title, summary, rating, rating explanation and findings.
- Every other community gets a deterministic report, with no LLM call.
- A failed report call falls back to the deterministic report, and the run report lists each failed community.
- Each community's title and summary are embedded, so communities can be found by vector search.
- Communities are stored as `Community` nodes linked from their entities by `MEMBER_OF` edges, and a new run replaces the previous partition in one transaction.
- The `HYBRID_RERANKED` and `GRAPH_EXPAND` recipes add the reports of communities that overlap the entities found.
- The `THEMATIC` recipe searches community reports directly, for broad questions.
- The report LLM reads the same `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL_ID` settings that extraction uses.
- Clustering needs the `community` extra, and LLM-written reports need the `llm` extra.

Read more: [communities](https://ontogr.github.io/agentic-graphrag/stable/concepts/communities) and [detect communities](https://ontogr.github.io/agentic-graphrag/stable/guides/detect-communities).

### Search, evidence and citations

- Passage search runs full-text search, vector search, or both, and fuses the two rankings with reciprocal rank fusion.
- Superseded, in-flight and out-of-scope passages are filtered inside the query, so every result is text the caller may read.
- Fetching an evidence id returns the exact text behind it, marked as truncated or partial when the requested range is not fully covered.
- Each evidence id is a version-specific reference, so a citation from an earlier document version still resolves and is labelled as superseded.
- Entity search finds entities by name and by meaning, and lists the passages in scope that mention each one.
- Exploration follows entity relations up to two steps out, with fixed node and edge limits, and separates relations that a passage supports from bare graph connections.
- Navigation moves from a passage to its parent and sibling sections, its adjacent passages, or the table rows around it, within a character budget.
- Citation checks verify that every cited evidence id was fetched in the caller's scope. They report ids that were not fetched, that name another document, or that are malformed.
- Cited answers render with numbered source references and a Sources list, and a source is linked only when it has an absolute HTTP(S) address.
- A failed search leg and every truncation are reported in the result, so an incomplete result is not mistaken for an empty one.
- `SearchEngine` runs named recipes over entity, chunk and community search, with an optional graph walk and a cross-encoder or graph-distance reranker.

Read more: [retrieval](https://ontogr.github.io/agentic-graphrag/stable/concepts/retrieval) and [retrieve and answer](https://ontogr.github.io/agentic-graphrag/stable/guides/retrieve-and-answer).

### The built-in agent

- `build_agent` returns one DeepAgents-based agent, bound at build time to a fixed set of document keys, a project id and an agent id.
- The evidence tools of the agent (discovery, entity search, graph exploration, navigation and passage fetch) read only the documents in its scope.
- Each run returns a status (`answered`, `insufficient_evidence`, `partial`, `partial_retrieval`, `budget_exhausted` or `recording_failed`), the answer with numbered references, and the fetched citations.
- Citations are checked against passages fetched in the same run, and one repair pass asks the model to fix any that fail.
- The messages, tool calls and tool results of the run are saved to the task's event log as the run goes, with each payload capped at 32,000 characters.
- A run stops at a LangGraph step limit (50 by default) or a tool-call limit (20 by default) and reports `budget_exhausted`.
- A run on an existing task name resumes that task. Steps left in progress are marked unknown, and completed step results are reused when their documents are still in scope.
- The model can be one client, a fallback chain, or a round-robin rotation over Anthropic, OpenAI, OpenAI-compatible and Google AI clients.
- A caller can pass an OpenTelemetry tracer to `build_agent`, and no global tracer is installed.
- The agent can record task steps, decisions and decision reviews with typed supports, and a decision cannot rest on support that needs review.

Read more: [the agent loop](https://ontogr.github.io/agentic-graphrag/stable/concepts/agent-loop) and [trace an agent run](https://ontogr.github.io/agentic-graphrag/stable/guides/trace-an-agent-run).

### Tasks and decisions

- A task has a goal, an append-only log of messages, tool calls, tool results and notes, and named steps marked completed, failed, in progress, unknown or not started.
- A named task resumes from a bounded view that lists its goal, step counts, active decisions and decisions needing review, without event bodies.
- A decision records a conclusion, rationale, assumptions, open questions and supports. A support can cite a document passage, a task event or another active decision.
- Decisions are active when recorded. They are superseded or rejected explicitly, and the earlier record and its support history are kept.
- When a document gets a new version or is removed, every active decision that cites it is flagged for review, with the reason recorded.
- Review spreads only along explicit decision dependencies, in bounded batches, with a queue stored in the graph so an interrupted run continues.
- A decision is reaffirmed only when each cited document is fetched at its current version and each decision it depends on is active and clear.
- Active decisions that give different conclusions for the same choice key in different tasks are listed as conflicts.
- Active decisions in the same project can be searched as precedents, each with the goal of the task that recorded it.
- A write that reuses a request id is replayed instead of recorded twice, and a reused id with different arguments is refused.

Read more: [connected memory](https://ontogr.github.io/agentic-graphrag/latest/guides/connected-memory).

### The MCP server

- The `agrag-mcp` command runs a local stdio MCP server over the configured document set.
- Evidence search, exact fetch, navigation and citation checks are separate tools.
- The document keys and project identity come from server environment variables, and tool arguments cannot change them.
- The server starts read-only, and write tools are not registered unless the deployer enables them.
- Task and decision reads and writes work in a configured project, and decision rejection needs a separate switch.
- Decisions and step support can cite only evidence that the same server process fetched in full.
- Each tool result has a size cap, and search and fetch report when items were dropped.
- Memory and entity reads have a per-request deadline that is set in configuration.
- Logs go to stderr, so the stdio protocol stream stays clean.
- Semantic search reports a dimension mismatch, and hybrid search falls back to lexical hits with a named failure.
- Each write call takes a request id of up to 64 characters that a client can reuse when it retries.
- The server instructions tell clients that a valid citation shows traceability and not support.

Read more: [connected memory](https://ontogr.github.io/agentic-graphrag/latest/guides/connected-memory).

### Tracing and run reports

- An OpenTelemetry tracer can be passed to `Graph`, `build_agent`, the stores, the embedders and the extractors. With no tracer, nothing is recorded and no global provider is installed.
- Ingestion spans cover loading, chunking, extraction, resolution, merge and storage writes, under the `agrag.ingestion.*`, `agrag.extraction.*`, `agrag.resolution.*`, `agrag.merge.*` and `agrag.storage.*` names.
- Each LLM call produces a call span, one span per attempt and one span per provider request, with token counts where the provider reports them.
- Search produces a root span that records the query, the scope, and the id, score, kind and text of every result.
- Each `Graph.add` call returns an `AddResult` with statistics per stage for ingestion, chunking, extraction, resolution, merge and storage.
- Per-item failures come back as records with the item id, error type and message, plus the trace and span ids when tracing is on, capped at 200 per stage.
- Dropped relations and entities are counted by kind, label and reason in `DroppedCount` records.
- Agent runs add OpenInference spans for tool and model calls under the caller's active span.
- Quarantined sources are listed in the ingestion stats with their error message and trace ids.
- Graph-store spans record query text and parameter values, except vector values and full-text search terms.
- Spans carry the full question, prompt, response and evidence text, and the library has no switch to remove it.

Read more: [observability](https://ontogr.github.io/agentic-graphrag/stable/concepts/observability) and [trace spans](https://ontogr.github.io/agentic-graphrag/stable/reference/trace-spans).

### Evaluation

- `agrag.eval` scores answers for correctness, faithfulness, context precision, context recall and citation accuracy, using DeepEval metrics and a judge model that you choose.
- It checks each cited sentence of an agent answer against the evidence that sentence cites, and marks citations to evidence the run never fetched as unsupported.
- It scores entity and relation extraction against hand-written gold annotations, with exact and overlap-based matching shown side by side.
- It scores entity resolution clusters with B-cubed and pairwise metrics.
- It scores agent runs from OpenTelemetry spans, covering expected tool use, task completion and a judged trajectory quality.
- It measures verifier calibration with per-class precision, recall and F1, a macro F1 and a confusion matrix, without a judge model.
- A judge can be built from any OpenAI-compatible endpoint, configured with `EVAL_JUDGE_*` variables that fall back to the shared `LLM_*` variables.
- An example script runs the answer metrics on your own documents and questions and prints a score table.
- Any scoring function can be wrapped as a DeepEval metric, so custom scores report through the same `evaluate()` call as the built-in metrics.

Read more: [score Agentic GraphRAG on your questions](https://ontogr.github.io/agentic-graphrag/stable/guides/score-agrag-on-your-questions).

### Configuration

- Every component reads environment variables or a `.env` file in the working directory, with a prefix for each area such as `NEO4J_`, `EMBEDDING_` and `EXTRACTION_`.
- One OpenAI-compatible endpoint can serve extraction, the agent and the evaluation judge through `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL_ID`. Each role can also have its own variables.
- Schemas that declare labels, relation types or property names that the graph uses for its own records are rejected.
- Stored fingerprints detect changes to the schema structure and the extraction settings, so an update rechunks, re-extracts in place, or skips work as the change requires.
- Each document has a stable graph node id derived from its document key, and chunk ids derive from the document version, the chunker settings and the position.
- Every record is validated when it is built, including character offsets, page spans, heading paths and evidence reference forms.
- Entity and relation thresholds can be tuned per label, and a budget caps how many chunks an LLM may read.
- Backends install through named extras, so you add only the ones you need.

Read more: [configuration reference](https://ontogr.github.io/agentic-graphrag/stable/reference/configuration).

## Supported formats

| Format | Extension(s) | Loader |
| --- | --- | --- |
| Plain text and logs | `.txt`, `.log` | Core |
| XML | `.xml` | Core |
| Markdown | `.md`, `.markdown` | Docling |
| AsciiDoc | `.adoc`, `.asciidoc` | Docling |
| HTML | `.html`, `.htm` | Docling |
| CSV / TSV | `.csv`, `.tsv` | Core, one document per row or one for the table |
| JSON | `.json` | Core, record-aware |
| JSON Lines | `.jsonl`, `.ndjson` | Core, one document per row |
| PDF | `.pdf` | Docling, needs the `docling` extra |
| Word | `.docx` | Docling |
| PowerPoint | `.pptx` | Docling |
| Excel | `.xlsx` | Docling |
| Images | `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp` | Docling, needs the `docling` extra |
| Chat exports | `.json`, `.jsonl`, `.ndjson` | Chat loader, which you pass for a single file |

Docling reads every rich format. The core readers keep plain text, XML, and the record formats, so a CSV row keeps its identity. Docling without the `docling` extra reads Markdown, HTML, AsciiDoc, Word, PowerPoint, and Excel files. The extra adds the layout and table models for PDF and image files.

## Project structure

```text
agrag/
├── common/data_models/   # documents, chunks, schemas, tasks, decisions and evidence records
├── loaders/              # core corpus readers and the Docling loaders
├── chunking/             # the section chunker
├── schema/               # schema loading, presets and schema format export
├── candidates/           # out-of-schema candidate capture, review and conversion
├── ingestion/            # Graph API, extraction, resolution, community detection and pipeline stages
├── embedding/            # dense embedding interfaces
├── graphdb/              # graph-store interface and Neo4j backend
├── cypher/               # validated Cypher builders
├── retrieval/            # search methods, retrievers, recipes and rerankers
├── evidence/             # passage discovery, fetch, navigation and citation checks
├── memory/               # tasks, events, steps and decisions
├── agents/               # the task-scoped agent, its tools and event handling
├── mcp_server/           # the agrag-mcp server
├── eval/                 # metrics for answers, extraction, resolution and agent runs
├── llm/                  # BAML sources, generated client and provider routing
└── observability.py      # OpenTelemetry helpers

tests/
├── unit/                 # isolated tests with external services mocked
└── integration/          # live backend tests against Docker services
```

## Development

```bash
git clone https://github.com/ontogr/agentic-graphrag.git
cd agentic-graphrag
make sync
make lint-check
make lint-typing
make test
```

Integration tests run against a local Neo4j service:

```bash
make dev-services-up
make test-integration
make dev-services-down
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, test conventions, and pull request guidelines.

## References

The work below shaped the design of Agentic GraphRAG.

<details>
<summary>Papers and projects</summary>

- [Microsoft GraphRAG](https://arxiv.org/abs/2404.16130): hierarchical communities and community reports
- [Graphiti](https://github.com/getzep/graphiti): layered graph search and entity-aware retrieval
- [Cognee](https://github.com/topoteretes/cognee): data pipelines, graph memory, and consolidation
- [KG-Gen](https://github.com/stair-lab/kg-gen): knowledge-graph extraction and alias deduplication
- [FalkorDB GraphRAG SDK](https://github.com/FalkorDB/GraphRAG-SDK): graph-native retrieval and entity resolution
- [Neo4j GraphRAG](https://github.com/neo4j/neo4j-graphrag-python): Neo4j retrieval and vector integration
- [LightRAG](https://github.com/HKUDS/LightRAG): graph and vector retrieval
- [PathRAG](https://github.com/BUPT-GAMMA/PathRAG): relational-path retrieval
- [GLiNER](https://arxiv.org/abs/2311.08526): generalist zero-shot information extraction
- [BAML](https://boundaryml.com/), [Docling](https://github.com/docling-project/docling), and [Chonkie](https://github.com/chonkie-inc/chonkie)

</details>

## License

This project is licensed under the [Apache License 2.0](LICENSE).
