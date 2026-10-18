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

Agentic GraphRAG keeps everything in a single graph with three connected layers. The first layer holds your documents, with their sections, tables, and passages, and the people, organizations, products, and other entities found in them. The second holds the work your agents do, including named tasks, the steps they take, and a log of what happened. The third holds the decisions your agents make, each one tied to the passages, events, or earlier decisions it rests on.

Because the layers are connected, everything can be traced back to its source. A passage knows its document, its place in the document's structure, and the exact version it came from, with page positions for PDFs. A relation between two entities points to the passages that support it, and a decision points to the text it was based on. The graph also keeps the history of each document, so a citation to an older version still leads to the text that was cited.

<details>
<summary>Diagram prompt: the three layers of the graph</summary>

Draw a layered graph diagram with three horizontal bands, labeled from bottom to top: "Knowledge layer", "Task layer", and "Decision layer". Use one color per band and a legend for solid edges and dashed property references.

Knowledge layer, documents and passages: a `Document` node with `HAS_CHILD {order}` edges to `Section` nodes. `Section` nodes nest through `HAS_CHILD` and have `Table` and `Figure` children. Annotate `Section` with "heading, depth, range", `Table` with "columns, row count, caption", and `Figure` with "caption, location". `Chunk` nodes hang under sections or tables through `HAS_CHILD`, and consecutive chunks are joined by `NEXT_CHUNK`. Annotate one `Chunk` with its stored fields: heading path, section ids, content hash, and character span or page span with bounding box. Show a `HAS_PART` edge from `Document` to a `Chunk`, with `valid_at`, `invalid_at`, and `version_id` written on the edge. Show a `DocumentActivation` node joined to `Document` by `HAS_ACTIVATION`, annotated with `activation_seq`, `verb` (add, update, delete), `content_hash`, and `version_id`.

Knowledge layer, entities: two entity nodes with schema labels, for example `Organization` and `Product`, joined by a relation edge that carries `source_chunk_ids`. A `MENTIONED_IN` edge runs from a `Chunk` to each entity it mentions. Two similar entities are joined by a `MATCHES` edge with `comparator`, `score`, and `reasoning`, and both are joined to a `ResolvedEntity` node by `RESOLVED_AS`.

Task layer: `MemoryTask` with `HAS_EVENT` to `MemoryEvent` and `HAS_STEP` to `MemoryStep`. Annotate `MemoryStep` with "state, result event". Decision layer: `MemoryDecision` nodes, reached from `MemoryTask` by `MADE` (this edge crosses the band boundary). `MemoryDecision` has `HAS_SUPPORT` to `MemorySupport`, and `DEPENDS_ON` and `SUPERSEDES` edges to other decisions. Draw one dashed line, not an edge, from `MemorySupport` down to the `Document` node, labeled "property reference: document_node_id, chunk_id or char span, content_hash, recorded_activation_seq". Draw two more dashed lines from `MemorySupport`, one to `MemoryEvent` labeled "event_id" and one to another `MemoryDecision` labeled "target_decision_id".

Show only the elements named above.

</details>

### Build the graph around your own schema

You describe the kinds of things that matter to you, such as people, contracts, or products, and the relations between them. You can write that schema in code or in a configuration file, or start from a ready-made preset and extend it. Extraction runs on your machine first, so you can build a graph without an LLM. When the local model is unsure about a passage, an LLM can read it, and you decide how much of each batch the LLM may read. Anything the models find that your schema does not cover is saved for review instead of being discarded, and approved items become part of your schema and your graph.

Duplicates are handled with care. Agentic GraphRAG recognizes that "Acme Corp" and "Acme Corporation" are the same company by starting with cheap checks and asking an LLM only about the pairs that remain unclear. A match is stored as a link between the two entities, so the originals stay in the graph and any match can be undone. You can also preview a cleanup of the whole graph before you apply it.

<details>
<summary>Diagram prompt: the extraction and resolution pipeline</summary>

Draw a left to right flowchart with two swim lanes, "Extraction" and "Resolution".

Extraction lane: "Schema load" feeds "Chunks". A mode switch with three labeled outputs follows: "gliner (local)", "hybrid (default)", and "llm (chunks of 8 or more words)". The gliner and hybrid paths go to "GLiNER primary pass (every chunk)", then to "Schema validation". For hybrid, add a decision diamond "Escalate?" with three labeled inputs: "lowest kept score below 0.75", "label declares properties", and "no entity found in a chunk of 8 or more words". A "Budget (default 20% of each batch), weakest first" box limits the yes branch. The yes branch goes to "LLM extraction, given the GLiNER entities", then "Combine with GLiNER result", then back into "Schema validation". Add a side note "No LLM configured: hybrid runs on GLiNER alone". From "Schema validation", draw two outputs: "Entities and relations" and "Candidates (relations, properties, and borderline entities outside the schema)". Candidates go to "List, approve, or reject", then "Schema patch file", then "You apply the patch to your schema", then "convert_candidates writes graph data".

Resolution lane: "Entities and relations" enter a ladder of tiers: "Exact match", "Fuzzy match (0.97 or more)", "Embedding similarity (0.95 or more matches, 0.80 to 0.95 continues)", "Cluster tight groups", and "LLM check (up to max_llm_pairs per label)". Each tier has an arrow "matched" to a box "MATCHES edge (comparator, score, reasoning)" and an arrow "undecided" to the next tier. Only the exact tier also points to "Merge entity". Finish with "ResolvedEntity groups matched entities". Add two side paths: "deactivate_match undoes a match, originals stay" and "consolidate() previews a graph-wide pass, apply=True writes it".

Show only the elements named above.

</details>

### Search your documents and read the evidence

Agents search your documents by keyword, by meaning, or by both. A search returns short previews, each with an identifier for its passage, and a separate step fetches the exact text. You decide which documents an agent may read, and that choice is made outside the model, so the model can only work inside it. Search reads the source text directly, so a passage is still found when extraction missed the fact it contains.

From any passage, an agent can move to the surrounding section, the neighboring passages, or the rows around a table cell, which keep their column headers. It can also look up an entity, see the passages that mention it, and follow its relations a few steps out. Each relation is marked as backed by a passage or as a connection without direct text. Every result says when something was cut off or part of the search failed, so an incomplete result is never mistaken for an empty one.

<details>
<summary>Diagram prompt: from a question to cited evidence</summary>

Draw a top to bottom flow. At the top, a box "Caller sets document scope (outside the model)" feeds every step below with a thin line. Then: "Question", then "Search evidence" with three labeled legs "keyword (full-text)", "meaning (vector)", and "hybrid (reciprocal rank fusion)", restricted to "current text only". The output is "Hits: evidence id, document, snippet, ordering score". Beside the output show two distinct results: "No match: empty list" and "Failed leg or index not ready: reported separately". From the hits draw "Fetch evidence", returning "Exact text up to a size limit, citation markdown". Beside the fetch step draw three optional side paths. First, "navigate" with the six relations "parent, children, siblings, previous, next, table context", annotated "table results repeat header rows" and "reports when cut". Second, "find_entities" with "filter by label" returning "supporting passages as evidence ids" and a separate "unsupported" marker for entities without a visible passage. Third, "explore" with "up to 2 steps", returning edges of two kinds, "assertion (has supporting passages)" and "path (no direct support)", plus "names the limit that cut the result". Draw an inset that shows the evidence id as three parts: "document", "version hash", "span or chunk". Show an out-of-scope id leading to "unavailable".

Show only the elements named above.

</details>

### Pick up a task where it stopped

Agents can give their work a name and come back to it later. The graph keeps the messages, tool calls, and results of a task along with its steps. When the task resumes, the agent sees the goal, the progress so far, and the decisions already made, and it reuses finished work that is still valid. A step that was interrupted is marked as unknown so that it can be run again, and repeating a write after a failure never records it twice.

A decision records a conclusion, the reasoning, the assumptions, and the open questions, along with the passages, events, or earlier decisions it relies on. When a document behind a decision is updated or removed, the decision is flagged for review, and so are the decisions that depend on it. A reviewer can reaffirm the decision after reading the current text, or replace it with a new one that explains the change. The earlier version stays in the history. Agents can also search past decisions in the same project and use them as precedent.

<details>
<summary>Diagram prompt: resuming a task and reviewing a decision</summary>

Draw two connected panels.

Panel 1, "Resume a task", as a numbered vertical sequence: 1 "Load the task by name, or create it from the question", 2 "Mark interrupted steps unknown so the agent can run them again", 3 "Work through a batch of pending review flags", 4 "Read the bounded view: goal, step counts by state, active decisions, decisions needing review, conflicts", 5 "Append the new question as a message event", 6 "Show completed step results with their reuse status", 7 "Start with empty evidence state, so the agent fetches evidence in the new run before citing".

Panel 2, "Source change review", as a flow: "Document update or delete commits" leads to "Decisions with a support on that document are flagged (same transaction)". Then "Flag spreads along DEPENDS_ON edges to dependent decisions". Then three exits from a flagged decision: "Reaffirm after fetching the current text (earlier supports kept as history)", "Supersede with explanation (new revision, SUPERSEDES edge)", and "Reject (when the operator enables it)".

Between the panels draw a small graph inset using the labels `MemoryTask`, `MemoryEvent`, `MemoryStep`, `MemoryDecision`, `MemorySupport`, `HAS_EVENT`, `HAS_STEP`, `MADE`, `HAS_SUPPORT`, and `DEPENDS_ON`. Draw `MemorySupport` pointing to a `Document` node with a dashed line, not an edge, labeled "property reference: document_node_id, chunk_id or span, content_hash, recorded_activation_seq".

Show only the elements named above.

</details>

### Use the built-in agent or any MCP client

The built-in agent searches your documents, reads passages, and answers with numbered sources. Before an answer is returned, each citation is checked. The passage must have been read during that run, it must belong to the documents the agent may use, and it must match the version cited. If a citation fails the check, the agent gets one chance to fix it. Every run ends with a status that tells you whether the agent answered, found too little evidence, or reached a limit, and you set how many steps and tool calls a run may use. You can choose Anthropic, OpenAI, Google, or any OpenAI-compatible model, with fallback between them.

The same tools are available to other agents through a local MCP server. It starts read-only and shows only the documents you choose, and you decide whether a client may record tasks and decisions. Runs can be traced with OpenTelemetry, and the evaluation tools score answers, citations, and agent runs on your own questions.

<details>
<summary>Diagram prompt: agent run with trust boundaries</summary>

Draw a flow with a dashed rectangle labeled "Operator-controlled: settings and code" around the boxes "Document scope", "project_id and agent_id", "read_only flag", the "Graph store", and "Citation checker". Outside it, draw a dashed rectangle labeled "Model and data: model output, source passages, task events, tool results".

Inside the flow, in order: "Question", "Load or create the task", "Mark interrupted steps unknown", "Agent loop (up to 50 steps and 20 tool calls)" containing the evidence tools "discover_evidence", "fetch_evidence", "navigate", "find_entities", "explore", "check_citations", the memory tools "get_task", "list_decisions", "search_decisions", "record_decision", "set_step", and a side box "Each message and tool result is recorded as a task event". Then "Parse citations", "Check citations" with the verdicts "valid", "unavailable", "not fetched", and "malformed", then a decision diamond "Any invalid?" whose "yes" branch goes to "One repair turn" and back to "Check citations". The "no" branch goes to "Render numbered sources" and "Result: answer, status, fetched evidence for valid citations, invalid citations, recording failures, task name and last event".

Add a second small panel "MCP server" with a client box on the left. Show three groups of tools: "Evidence reads (always on)", "Memory reads (need project_id and agent_id)", and "Writes (read_only=false, reject needs allow_reject)". Label the server "document scope fixed at startup".

Show only the elements named above.

</details>

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
