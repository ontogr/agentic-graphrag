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

### What the graph stores

The graph keeps three connected layers. The knowledge layer holds your documents, their passages, and the entities and relations extracted from them. The task layer holds the tasks, steps, and events of your agents. The decision layer holds their decisions and the supports that tie them to passages, events, and other decisions. Provenance connects the layers, so each fact and each decision records what supports it.

- **Documents and passages.** Loaders read prose, office documents, structured records, and chat exports. Each document keeps a section tree of `Section`, `Table`, and `Figure` nodes. Section-aware chunking creates `Chunk` nodes in reading order, linked by `NEXT_CHUNK`.
- **Provenance on every passage.** A chunk stores its heading path, its content hash, and either character spans or page spans with bounding boxes.
- **Knowledge.** Entities carry the labels from your schema, and a `MENTIONED_IN` edge joins each chunk to the entities it mentions. Each relation lists the chunks that support it, and each match edge between similar entities records the comparator, the score, and the reasoning.
- **Versions.** Each document keeps an activation log, and an update creates a new version of its passages.
- **Tasks and decisions.** A decision support records the passage and the document version it was fetched from, as described under memory below.

<details>
<summary>Diagram prompt: the three layers of the graph</summary>

Draw a layered graph diagram with three horizontal bands, labeled from bottom to top: "Knowledge layer", "Task layer", and "Decision layer". Use one color per band and a legend for solid edges and dashed property references.

Knowledge layer, documents and passages: a `Document` node with edges `HAS_CHILD` to `Section` nodes. `Section` nodes nest through `HAS_CHILD` and also have `Table` and `Figure` children. `Chunk` nodes hang under sections or tables through `HAS_CHILD`, and consecutive chunks are joined by `NEXT_CHUNK`. Show a `HAS_PART` edge from `Document` to a `Chunk`, with the properties `valid_at`, `invalid_at`, and `version_id` written on the edge. Show a `DocumentActivation` node joined to `Document` by `HAS_ACTIVATION`. Annotate one `Chunk` with its stored fields: heading path, content hash, character span or page span with bounding box.

Knowledge layer, entities: two entity nodes with schema labels, for example `Organization` and `Product`, joined by a relation edge that carries `source_chunk_ids`. A `MENTIONED_IN` edge runs from a `Chunk` to each entity it mentions. Two similar entities are joined by a `MATCHES` edge with `comparator`, `score`, and `reasoning`, and both are joined to a `ResolvedEntity` node by `RESOLVED_AS`.

Task layer: `MemoryTask` with `HAS_EVENT` to `MemoryEvent` and `HAS_STEP` to `MemoryStep`. Decision layer: `MemoryDecision` nodes, reached from `MemoryTask` by `MADE` (this edge crosses the band boundary). `MemoryDecision` has `HAS_SUPPORT` to `MemorySupport`, and `DEPENDS_ON` and `SUPERSEDES` edges to other decisions. Draw one dashed line, not an edge, from `MemorySupport` down to the `Document` node, labeled "property reference: document_node_id, chunk_id or char span, content_hash, recorded_activation_seq".

Show only the elements named above.

</details>

### Tiered extraction and entity resolution

Extraction starts with a local GLiNER model and calls an LLM only for the chunks that need one. Resolution then connects duplicate entities in tiers, and the LLM judges only the pairs that cheaper tiers cannot settle.

- **Your schema sets the boundary.** Define it in Python, YAML, JSON, or Pydantic models, or start from a shipped preset. Entities with declared labels enter the graph, and relations and properties outside the schema become candidates that you can review.
- **Escalation is selective.** The default mode, `hybrid`, runs GLiNER on every chunk. A chunk goes to the LLM when its lowest kept score is below the threshold, when one of its labels declares properties, or when a chunk of eight words or more yields no entity. Each batch caps how many chunks escalate, and the LLM result is combined with the GLiNER result. With no LLM configured, `hybrid` runs on GLiNER alone.
- **Approved candidates become schema patches.** Approving a candidate produces a schema patch that you apply to your schema.
- **Resolution runs in tiers.** It tries an exact match, then fuzzy string matching, then embedding similarity, then clustering, and last an LLM check. The `max_llm_pairs` setting caps the LLM pairs per label.
- **Matches are reversible.** Exact matches merge. Other matches become match edges, and a resolved entity groups the matched entities. You can deactivate a match, and the original entities stay in the graph.
- **Local by default.** GLiNER extraction and embeddings run on your machine.

<details>
<summary>Diagram prompt: the extraction and resolution pipeline</summary>

Draw a left to right flowchart with two swim lanes, "Extraction" and "Resolution".

Extraction lane: "Schema load" feeds "Chunks". Chunks go to "GLiNER primary pass (every chunk)", then to "Schema validation". Add a decision diamond "Escalate?" with three labeled inputs: "lowest kept score below threshold", "label declares properties", and "no entity found in a chunk of 8 or more words". A "Per-batch budget" box limits the "yes" branch. The "yes" branch goes to "LLM extraction", then "Combine with GLiNER result", then back into "Schema validation". The "no" branch skips the LLM. Show a side note "No LLM configured: hybrid runs as gliner". From "Schema validation", draw two outputs: "Entities and relations" and "Candidates (off-schema relations, undeclared properties, borderline entities)". Candidates go to "Review" and then "Schema patch for you to apply". Drop undeclared entity labels at validation with a small "dropped" arrow.

Resolution lane: "Entities and relations" enter a ladder of tiers: "Exact match", "Fuzzy match (0.97 or more)", "Embedding similarity (0.95 or more matches, below 0.80 dropped)", "Cluster cut", and "LLM check (capped by max_llm_pairs per label)". Each tier has an arrow "matched" to a box "Match edge (comparator, score, reasoning)" and an arrow "undecided" to the next tier. Only the exact tier also points to "Merge raw entity". Finish with "ResolvedEntity groups matched entities" and a note "Deactivate a match without losing originals".

Show only the elements named above.

</details>

### Retrieval

The agent and the MCP server use one evidence path. Search finds passages within a document scope that the caller fixes. It reads current text only and combines keyword and meaning search. Each hit carries an evidence id, and a separate fetch call returns the exact text.

- **Search by keyword, meaning, or both.** Hybrid search runs both and merges the ranked lists with reciprocal rank fusion. A hit holds the document, a snippet, and an evidence id. Its score orders the hits.
- **Clear search results.** A search with no match returns an empty list, and a search leg that fails or an index that is not ready is reported on its own.
- **Search reads the source directly.** Passages are searched as written, so source text stays findable even when extraction missed a fact.
- **The caller fixes the scope.** The caller binds the document scope outside the model, so the model works only inside it.
- **Fetch reads the source.** Fetch returns the exact text behind an evidence id, up to a size limit, with a ready citation. An id names the document, the version, and the span or chunk, so a citation points to one place in one version.
- **Navigate around a passage.** `navigate` moves from a passage to its parent section, to other passages in the same section, to neighboring sections, to the previous or next passage, or to the surrounding table rows. Table results repeat the header rows, so a cell never appears alone. Results are bounded, and each result says if a limit applied.
- **Follow entities back to text.** `find_entities` finds entities by name or meaning, can filter by label, and returns the passages that support each one. `explore` follows relations up to two steps. Each edge is an assertion with supporting passages or a path, and the result names any limit that applied.

<details>
<summary>Diagram prompt: from a question to cited evidence</summary>

Draw a top to bottom flow. At the top, a box "Caller sets document scope (outside the model)" feeds every step below with a thin line. Then: "Question", then "Search evidence" with three labeled legs "keyword (full-text)", "meaning (vector)", and "hybrid (reciprocal rank fusion)", restricted to "current text only". The output is "Hits: evidence id, document, snippet, ordering score". Beside the output show two distinct results: "No match: empty list" and "Failed leg or index not ready: reported separately". From the hits draw "Fetch evidence", returning "Exact text up to a size limit, citation markdown". Beside the fetch step draw three optional side paths. First, "navigate" with the six relations "parent, children, siblings, previous, next, table context", annotated "table results repeat header rows" and "reports when cut". Second, "find_entities" with "filter by label" returning "supporting passages as evidence ids" and a separate "unsupported" marker for entities without a visible passage. Third, "explore" with "up to 2 steps", returning edges of two kinds, "assertion (has supporting passages)" and "path (no direct support)", plus "names the limit that cut the result". Draw an inset that shows the evidence id as three parts: "document", "version hash", "span or chunk". Show an out-of-scope id leading to "unavailable".

Show only the elements named above.

</details>

### Memory and resuming tasks

The task and decision layers sit on top of the knowledge layer. A named task keeps an append-only log of events, a list of steps, and decisions. A resumed task starts from that record instead of starting over.

- **Resuming returns a bounded view.** The view lists the goal, step counts, active decisions, and decisions that need review. Completed step results are reused unless their support is no longer current, was redacted, or is outside the scope.
- **Fresh evidence on resume.** A resumed agent fetches the passages it cites in the new run, so each citation is checked against evidence from that run.
- **Each decision links back to the knowledge layer.** A support stores the document id, the span or chunk, the content hash, and the activation sequence of the version the agent fetched. These values let the graph detect when the text behind a decision has changed.
- **Source changes flag decisions.** When a cited document is updated or deleted, the decisions that cite it are flagged for review in the same transaction. The flag spreads along explicit dependencies between decisions.
- **Reviews end in a decision.** Reaffirm a decision at the current version, replace it with an explanation, or reject it. A replaced decision remains in its task's history.
- **Recording differs by client.** The built-in agent records messages, tool calls, and tool results automatically. MCP clients record events through explicit tools. Access is scoped to the project.

<details>
<summary>Diagram prompt: resuming a task and reviewing a decision</summary>

Draw two connected panels.

Panel 1, "Resume a task", as a numbered vertical sequence: 1 "Load task by name (create it if new)", 2 "Reset in-progress steps to unknown", 3 "Work through a batch of pending review flags", 4 "Read the bounded view: goal, step counts, active decisions, decisions needing review", 5 "Append the new question as a message event", 6 "Show completed step results, marking any with outdated, redacted, or out-of-scope support as not reusable", 7 "Start with empty evidence state, so the agent fetches evidence again before citing".

Panel 2, "Source change review", as a flow: "Document update or delete commits" leads to "Decisions with a support on that document are flagged (same transaction)". Then "Flag spreads along DEPENDS_ON edges to dependent decisions". Then three exits from a flagged decision: "Reaffirm at current version", "Supersede with explanation", and "Reject".

Between the panels draw a small graph inset using the labels `MemoryTask`, `MemoryEvent`, `MemoryStep`, `MemoryDecision`, `MemorySupport`, `HAS_EVENT`, `HAS_STEP`, `MADE`, `HAS_SUPPORT`, and `DEPENDS_ON`. Draw `MemorySupport` pointing to a `Document` node with a dashed line, not an edge, labeled "property reference: document_node_id, chunk_id or span, content_hash, recorded_activation_seq".

Show only the elements named above.

</details>

### Citation-tracked agent and MCP with governance and provenance

The built-in agent and the MCP server expose the same evidence tools over the graph built from your schema. Answers cite passages by evidence id, and the tools check each citation before the answer is returned.

- **Each valid citation traces to its source.** A citation is valid when the passage was fetched in the current run, lies in scope, and matches the cited content hash.
- **Citations are repaired once.** If a check fails, the agent gets one repair turn. Valid citations render as numbered sources.
- **Bounded runs.** The agent stops at 50 steps or 20 tool calls by default. Choose Anthropic, OpenAI, OpenAI-compatible, or Google models, with fallback or round-robin routing. The agent records tasks and decisions directly.
- **MCP starts read-only.** Write tools are registered only when you enable them, and rejecting a decision needs its own flag. The server runs locally over stdio, requires a document scope at startup, and fixes that scope for the whole session.
- **Governance by configuration.** The operator sets the document scope, the project, and the read-only flag. Evidence reads follow the document scope, and memory reads follow the project.
- **Runs expose their provenance.** A result includes the fetched evidence for each valid citation, the invalid citations, recording failures, and the task position.
- **Observe and evaluate.** Pass an OpenTelemetry tracer to record agent runs. Traces include the full prompts, questions, and evidence, so apply your telemetry controls. Evaluation tools score runs with your own data and judge model.
- **Configuration.** Settings come from environment variables and `.env` files where supported. You can also pass schemas, document scope, and components in Python.

<details>
<summary>Diagram prompt: agent run with trust boundaries</summary>

Draw a flow with a dashed rectangle labeled "Trusted: operator settings and code" around the boxes "Document scope", "project_id and agent_id", "read_only flag", the "Graph store", and "Citation checker". Outside it, draw a dashed rectangle labeled "Untrusted data: model output, source passages, task events, tool results".

Inside the flow, in order: "Question", "Load or create task", "Agent loop (up to 50 steps and 20 tool calls)" containing the tools "discover_evidence", "fetch_evidence", "navigate", "find_entities", "explore", "check_citations", the memory tools "get_task", "list_decisions", "record_decision", "set_step", and a side box "Each message and tool result is recorded as a task event". Then "Parse citations", "Check citations" with the verdicts "valid", "unavailable", "not fetched", and "malformed", then a decision diamond "Any invalid?" whose "yes" branch goes to "One repair turn" and back to "Check citations". The "no" branch goes to "Render numbered sources" and "Result: answer, status, valid citations with fetched evidence, invalid citations, recording failures, task position".

Add a second small panel "MCP server" with a client box on the left. Show three groups of tools: "Evidence reads (always)", "Memory reads (need project_id and agent_id)", and "Writes (only when read_only is off, reject needs a separate flag)". Mark the client as a separate trust boundary and label the server "document scope fixed at startup".

Show only the elements named above.

</details>

## Quickstart

Install graph storage, local extraction, and the built-in agent. This example uses the current `main` APIs:

```bash
uv pip install "agentic-graphrag[neo4j,extract,agents] @ git+https://github.com/ontogr/agentic-graphrag.git@main" --torch-backend=auto
```

You need Python 3.11+, a configured Neo4j database, and an LLM endpoint. The [setup guide](https://ontogr.github.io/agentic-graphrag/latest/get-started/quickstart) covers database and model configuration. Local models download on first use.

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

Reuse the project and task name to continue from recorded progress. For explicit decisions and source-change review, see the [connected-memory guide](https://ontogr.github.io/agentic-graphrag/latest/guides/connected-memory/). It runs the workflow against a pinned fixture from a repository checkout.

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
