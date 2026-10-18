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

- **Documents keep their structure.** Loaders read prose, office documents, structured records, and chat exports into a `Document` node with a tree of `Section`, `Table`, and `Figure` nodes. A section records its heading, depth, and range. A table keeps its column names, row count, and caption, and a figure keeps its caption and location.
- **Passages follow reading order.** Section-aware chunking creates `Chunk` nodes linked by `NEXT_CHUNK`. Each chunk carries its heading path and the sections it covers, so a passage shows where it sits in the document.
- **Every passage records where it came from.** A chunk stores its content hash and either character spans or page spans with bounding boxes.
- **Knowledge links back to passages.** Entities carry the labels from your schema, and a `MENTIONED_IN` edge joins each chunk to the entities it mentions. Each relation lists the chunks that support it, and each match edge between similar entities records the comparator, the score, and the reasoning.
- **Versions are logged.** `HAS_PART` edges record which version each part belongs to. Each add, update, and delete writes a `DocumentActivation` node with the verb and the content hash.
- **Tasks and decisions build on the knowledge layer.** A decision support records the passage and the document version it was fetched from, as described under memory below.

<details>
<summary>Diagram prompt: the three layers of the graph</summary>

Draw a layered graph diagram with three horizontal bands, labeled from bottom to top: "Knowledge layer", "Task layer", and "Decision layer". Use one color per band and a legend for solid edges and dashed property references.

Knowledge layer, documents and passages: a `Document` node with `HAS_CHILD {order}` edges to `Section` nodes. `Section` nodes nest through `HAS_CHILD` and have `Table` and `Figure` children. Annotate `Section` with "heading, depth, range", `Table` with "columns, row count, caption", and `Figure` with "caption, location". `Chunk` nodes hang under sections or tables through `HAS_CHILD`, and consecutive chunks are joined by `NEXT_CHUNK`. Annotate one `Chunk` with its stored fields: heading path, section ids, content hash, and character span or page span with bounding box. Show a `HAS_PART` edge from `Document` to a `Chunk`, with `valid_at`, `invalid_at`, and `version_id` written on the edge. Show a `DocumentActivation` node joined to `Document` by `HAS_ACTIVATION`, annotated with `activation_seq`, `verb` (add, update, delete), `content_hash`, and `version_id`.

Knowledge layer, entities: two entity nodes with schema labels, for example `Organization` and `Product`, joined by a relation edge that carries `source_chunk_ids`. A `MENTIONED_IN` edge runs from a `Chunk` to each entity it mentions. Two similar entities are joined by a `MATCHES` edge with `comparator`, `score`, and `reasoning`, and both are joined to a `ResolvedEntity` node by `RESOLVED_AS`.

Task layer: `MemoryTask` with `HAS_EVENT` to `MemoryEvent` and `HAS_STEP` to `MemoryStep`. Annotate `MemoryStep` with "state, result event". Decision layer: `MemoryDecision` nodes, reached from `MemoryTask` by `MADE` (this edge crosses the band boundary). `MemoryDecision` has `HAS_SUPPORT` to `MemorySupport`, and `DEPENDS_ON` and `SUPERSEDES` edges to other decisions. Draw one dashed line, not an edge, from `MemorySupport` down to the `Document` node, labeled "property reference: document_node_id, chunk_id or char span, content_hash, recorded_activation_seq". Draw two more dashed lines from `MemorySupport`, one to `MemoryEvent` labeled "event_id" and one to another `MemoryDecision` labeled "target_decision_id".

Show only the elements named above.

</details>

### Tiered extraction and entity resolution

Extraction starts with a local GLiNER model and calls an LLM only for the chunks that need one. Resolution then connects duplicate entities in tiers, and the LLM judges only the pairs that cheaper tiers cannot settle.

- **Three extraction modes.** Set `EXTRACTION_MODE` to `gliner` to run extraction locally, `hybrid` for local first with an LLM on weak chunks, or `llm` to send every chunk of eight words or more to the LLM. The default is `hybrid`.
- **Escalation follows a budget.** In `hybrid` mode a chunk is eligible for the LLM when its lowest kept score is below `escalation_threshold` (0.75), when a label declares properties, or when a chunk of eight or more words yields no entity. The weakest chunks go first, and `escalation_budget` (default 0.2, or `"all"`) caps the share of each batch. The run log reports the budget that would cover every eligible chunk.
- **The LLM builds on the local result.** It receives the GLiNER entities, and its answer is combined with the GLiNER result. With no LLM configured, `hybrid` runs on GLiNER alone.
- **Your schema governs the result.** Define it in Python, YAML, JSON, or Pydantic models, start from a preset such as `operations` or `legal`, or extend a base schema. Entities with declared labels enter the graph.
- **Candidates capture the rest.** Relations, properties, and borderline entities outside the schema are saved as candidates. List, approve, or reject them, and approval writes a schema patch that you apply to your schema. Then `convert_candidates` turns the approved candidates into graph data.
- **Resolution runs in tiers.** It tries an exact match, then fuzzy matching, then embedding similarity, then clustering of tight groups, and last an LLM check. The `max_llm_pairs` setting (default 500) caps the LLM pairs per label.
- **Matches are reversible.** Exact matches merge. Other matches become `MATCHES` edges, and a `ResolvedEntity` groups the matched entities. `deactivate_match` undoes a match, and the original entities stay in the graph.
- **Graph-wide passes preview first.** `consolidate()` previews a pass over the whole graph, and `consolidate(apply=True)` writes it.
- **Local by default.** GLiNER extraction and embeddings run on your machine.

<details>
<summary>Diagram prompt: the extraction and resolution pipeline</summary>

Draw a left to right flowchart with two swim lanes, "Extraction" and "Resolution".

Extraction lane: "Schema load" feeds "Chunks". A mode switch with three labeled outputs follows: "gliner (local)", "hybrid (default)", and "llm (chunks of 8 or more words)". The gliner and hybrid paths go to "GLiNER primary pass (every chunk)", then to "Schema validation". For hybrid, add a decision diamond "Escalate?" with three labeled inputs: "lowest kept score below 0.75", "label declares properties", and "no entity found in a chunk of 8 or more words". A "Budget (default 20% of each batch), weakest first" box limits the yes branch. The yes branch goes to "LLM extraction, given the GLiNER entities", then "Combine with GLiNER result", then back into "Schema validation". Add a side note "No LLM configured: hybrid runs on GLiNER alone". From "Schema validation", draw two outputs: "Entities and relations" and "Candidates (relations, properties, and borderline entities outside the schema)". Candidates go to "List, approve, or reject", then "Schema patch file", then "You apply the patch to your schema", then "convert_candidates writes graph data".

Resolution lane: "Entities and relations" enter a ladder of tiers: "Exact match", "Fuzzy match (0.97 or more)", "Embedding similarity (0.95 or more matches, 0.80 to 0.95 continues)", "Cluster tight groups", and "LLM check (up to max_llm_pairs per label)". Each tier has an arrow "matched" to a box "MATCHES edge (comparator, score, reasoning)" and an arrow "undecided" to the next tier. Only the exact tier also points to "Merge entity". Finish with "ResolvedEntity groups matched entities". Add two side paths: "deactivate_match undoes a match, originals stay" and "consolidate() previews a graph-wide pass, apply=True writes it".

Show only the elements named above.

</details>

### Retrieval

The agent and the MCP server use one evidence path. Search finds passages within a document scope that the caller fixes. It reads current text only and combines keyword and meaning search. Each hit carries an evidence id, and a separate fetch call returns the exact text.

- **Search by keyword, meaning, or both.** Hybrid search runs both and merges the ranked lists with reciprocal rank fusion. A hit holds the document, a snippet, and an evidence id. Its score orders the hits.
- **Clear search results.** A search with no match returns an empty list, and a search leg that fails or an index that is not ready is reported on its own.
- **Search reads the source directly.** Passages are searched as written, so source text stays findable even when extraction missed a fact.
- **The caller fixes the scope.** The caller binds the document scope outside the model, so the model works only inside it.
- **Fetch reads the source.** Fetch returns the exact text behind an evidence id, up to a size limit, with a ready citation. An id names the document, the version, and the span or chunk, so a citation points to one place in one version.
- **Navigate around a passage.** `navigate` moves from a passage to its parent section, to other passages in the same section, to neighboring sections, to the previous or next passage, or to the surrounding table rows. Table results repeat the header rows, so each cell appears with its header. Results are bounded, and each result says if a limit applied.
- **Follow entities back to text.** `find_entities` finds entities by name or meaning, can filter by label, and returns the passages that support each one. `explore` follows relations up to two steps. Each edge is an assertion with supporting passages or a path, and the result names any limit that applied.

<details>
<summary>Diagram prompt: from a question to cited evidence</summary>

Draw a top to bottom flow. At the top, a box "Caller sets document scope (outside the model)" feeds every step below with a thin line. Then: "Question", then "Search evidence" with three labeled legs "keyword (full-text)", "meaning (vector)", and "hybrid (reciprocal rank fusion)", restricted to "current text only". The output is "Hits: evidence id, document, snippet, ordering score". Beside the output show two distinct results: "No match: empty list" and "Failed leg or index not ready: reported separately". From the hits draw "Fetch evidence", returning "Exact text up to a size limit, citation markdown". Beside the fetch step draw three optional side paths. First, "navigate" with the six relations "parent, children, siblings, previous, next, table context", annotated "table results repeat header rows" and "reports when cut". Second, "find_entities" with "filter by label" returning "supporting passages as evidence ids" and a separate "unsupported" marker for entities without a visible passage. Third, "explore" with "up to 2 steps", returning edges of two kinds, "assertion (has supporting passages)" and "path (no direct support)", plus "names the limit that cut the result". Draw an inset that shows the evidence id as three parts: "document", "version hash", "span or chunk". Show an out-of-scope id leading to "unavailable".

Show only the elements named above.

</details>

### Memory and resuming tasks

The task and decision layers sit on top of the knowledge layer. A named task keeps an append-only log of events, a list of steps, and decisions. A resumed task starts from that record instead of starting over.

- **Name a task and return to it.** Resuming returns a bounded view with the goal, the step counts by state, the active decisions, the decisions that need review, and any conflicts. The events themselves are available on demand through `list_events` and `get_event`.
- **Steps save progress.** A step has a state and points to the event that holds its result. A completed result is reused when its supports are still current and in scope. A step that was running when the run stopped is marked unknown, so the agent can run it again.
- **Fresh evidence on resume.** A resumed agent fetches the passages it cites in the new run, so each citation is checked against evidence from that run.
- **Decisions carry their evidence.** A decision stores a conclusion, a rationale, assumptions, and open questions. Each document support stores the document id, the span or chunk, the content hash, and the activation sequence of the version the agent fetched, which links the decision back to the knowledge layer.
- **Source changes flag decisions.** When a cited document is updated or deleted, the decisions that cite it are flagged for review in the same transaction. The flag spreads along explicit dependencies between decisions.
- **Reviews end in an explicit action.** Reaffirm a flagged decision after fetching the current text, or supersede it with a new revision and an explanation. MCP clients can also reject a decision when the operator enables it. Reaffirming keeps the earlier supports as history, and a replaced decision remains in its task's history.
- **Precedent is searchable.** `search_decisions` searches the decisions of the project and returns each with the goal of its task.
- **Retries are safe.** Every write takes a `request_id`, so a retry returns the stored result.
- **Recording differs by client.** The built-in agent records messages, tool calls, and tool results automatically. MCP clients record events through explicit tools. Access is scoped to the project.

<details>
<summary>Diagram prompt: resuming a task and reviewing a decision</summary>

Draw two connected panels.

Panel 1, "Resume a task", as a numbered vertical sequence: 1 "Load the task by name, or create it from the question", 2 "Mark interrupted steps unknown so the agent can run them again", 3 "Work through a batch of pending review flags", 4 "Read the bounded view: goal, step counts by state, active decisions, decisions needing review, conflicts", 5 "Append the new question as a message event", 6 "Show completed step results with their reuse status", 7 "Start with empty evidence state, so the agent fetches evidence in the new run before citing".

Panel 2, "Source change review", as a flow: "Document update or delete commits" leads to "Decisions with a support on that document are flagged (same transaction)". Then "Flag spreads along DEPENDS_ON edges to dependent decisions". Then three exits from a flagged decision: "Reaffirm after fetching the current text (earlier supports kept as history)", "Supersede with explanation (new revision, SUPERSEDES edge)", and "Reject (when the operator enables it)".

Between the panels draw a small graph inset using the labels `MemoryTask`, `MemoryEvent`, `MemoryStep`, `MemoryDecision`, `MemorySupport`, `HAS_EVENT`, `HAS_STEP`, `MADE`, `HAS_SUPPORT`, and `DEPENDS_ON`. Draw `MemorySupport` pointing to a `Document` node with a dashed line, not an edge, labeled "property reference: document_node_id, chunk_id or span, content_hash, recorded_activation_seq".

Show only the elements named above.

</details>

### Citation-tracked agent and MCP with governance and provenance

The built-in agent and the MCP server expose the same evidence tools over the graph built from your schema. Answers cite passages by evidence id, and the tools check each citation before the answer is returned.

- **Evidence tools.** `discover_evidence` (named `search_evidence` on MCP), `fetch_evidence`, `navigate`, `find_entities`, `explore`, and `check_citations`. The `find_entities` tool filters by schema label.
- **Memory tools.** The agent reads tasks and decisions with `get_task`, `list_steps`, `list_events`, `get_event`, `get_decision`, `list_decisions`, `search_decisions`, `list_support_history`, and `list_decisions_for_review`. It records work with `set_step`, `record_decision`, `supersede_decision`, `reaffirm_decision`, and `continue_decision_review`.
- **Each valid citation traces to its source.** A citation is valid when the passage was fetched in the current run, lies in scope, and matches the cited content hash.
- **Citations are repaired once.** If a check fails, the agent gets one repair turn. Valid citations render as numbered sources.
- **Bounded runs.** The agent stops at 50 steps or 20 tool calls by default, and one evidence fetch returns up to 12,000 characters. The `AGENT_` environment variables change these limits.
- **Model choice.** Choose Anthropic, OpenAI, OpenAI-compatible, or Google models, with fallback or round-robin routing.
- **MCP starts read-only.** Set `AGRAG_MCP_READ_ONLY=false` together with `AGRAG_MCP_PROJECT_ID` and `AGRAG_MCP_AGENT_ID` to enable `create_task`, `record_event`, `set_step`, `record_decision`, `supersede_decision`, `reaffirm_decision`, and `continue_review_propagation`. Add `AGRAG_MCP_ALLOW_REJECT=true` to enable `reject_decision`.
- **Governance by configuration.** The operator sets the document scope with `AGRAG_MCP_SCOPE_DOCUMENT_KEYS`, along with the project and the read-only flag. The server runs locally over stdio and fixes the scope for the whole session. Evidence reads follow the document scope, and memory reads follow the project.
- **Runs expose their provenance.** A result includes the answer, a status, the fetched evidence for each valid citation, the invalid citations, recording failures, and the task name with its last event.
- **Observe and evaluate.** Pass an OpenTelemetry tracer to record one trace per run with model and tool spans. Traces include the full prompts, questions, and evidence, so apply your telemetry controls. Evaluation tools score answer correctness, faithfulness, context precision and recall, citation accuracy, and tool trajectories with your own data and judge model.
- **Configuration.** Settings come from environment variables and `.env` files where supported. You can also pass schemas, document scope, and components in Python.

<details>
<summary>Diagram prompt: agent run with trust boundaries</summary>

Draw a flow with a dashed rectangle labeled "Operator-controlled: settings and code" around the boxes "Document scope", "project_id and agent_id", "read_only flag", the "Graph store", and "Citation checker". Outside it, draw a dashed rectangle labeled "Model and data: model output, source passages, task events, tool results".

Inside the flow, in order: "Question", "Load or create the task", "Mark interrupted steps unknown", "Agent loop (up to 50 steps and 20 tool calls)" containing the evidence tools "discover_evidence", "fetch_evidence", "navigate", "find_entities", "explore", "check_citations", the memory tools "get_task", "list_decisions", "search_decisions", "record_decision", "set_step", and a side box "Each message and tool result is recorded as a task event". Then "Parse citations", "Check citations" with the verdicts "valid", "unavailable", "not fetched", and "malformed", then a decision diamond "Any invalid?" whose "yes" branch goes to "One repair turn" and back to "Check citations". The "no" branch goes to "Render numbered sources" and "Result: answer, status, fetched evidence for valid citations, invalid citations, recording failures, task name and last event".

Add a second small panel "MCP server" with a client box on the left. Show three groups of tools: "Evidence reads (always on)", "Memory reads (need project_id and agent_id)", and "Writes (read_only=false, reject needs allow_reject)". Label the server "document scope fixed at startup".

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
