<h1 align="center"><a href="https://github.com/ontogr/agentic-graphrag">Agentic GraphRAG</a></h1>

<h3 align="center">Context graphs that connect enterprise knowledge, conversation history, and decision traces.</h3>
<h4 align="center"><a href="https://ontogr.github.io/agentic-graphrag/">Documentation</a> | <a href="https://ontogr.github.io/agentic-graphrag/stable/get-started/quickstart">Quickstart</a> | <a href="https://ontogr.github.io/agentic-graphrag/stable/concepts/architecture">Concepts</a> | <a href="https://ontogr.github.io/agentic-graphrag/stable/guides/ingest-documents">Guides</a> | <a href="https://ontogr.github.io/agentic-graphrag/stable/api/">API reference</a></h4>


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

Agentic GraphRAG is an open source framework that connects enterprise knowledge, conversation history, and decision traces in one graph. Agents can find evidence, resume work across sessions, and review decisions when their sources change.

You add documents and the framework builds a knowledge graph shaped by your schema. Agents search the graph, read the exact passage behind each result, and cite it. They record decisions with supports that point to the evidence they rely on. Use the Python library, run the built-in agent, or connect your own agent through MCP.

> **[IMAGE: context-graph]**
> Alt text: Three connected graph layers. Enterprise knowledge contains documents, sections, chunks, entities, and relations. Conversation history contains tasks, events, and steps. Decision traces link conclusions to document passages, task events, and other decisions.
> Prompt: A clean technical diagram of three stacked, connected layers on a light background. The bottom layer, labeled "Enterprise knowledge", shows small nodes for documents, sections, chunks, entities, and relations joined by thin edges. The middle layer, labeled "Conversation history", shows a task node with a horizontal row of event nodes and a few step nodes. The top layer, labeled "Decision traces", shows decision nodes with arrows that reach down to a chunk, to an event, and to another decision. Flat vector style, one accent color per layer, no gradients, no people, wide 16:9 format.

## Features

### Build a knowledge graph from your documents

- Add a file, a folder, a glob pattern, a list of paths, plain text, or documents you built yourself.
- Plain text, logs, XML, Markdown, HTML, AsciiDoc, Word, PowerPoint, and Excel files are read directly. PDF and image support is an optional part of the install.
- Each row of a CSV or TSV file, and each record of a JSON or JSON Lines file, becomes its own document. A chat export is read with one section for each message.
- Headings, sections, tables, and figures stay in the graph, and PDF pages keep their page numbers and positions.
- Chunks follow the document structure. A table that fits stays whole, and a larger table is split into groups of rows that each repeat the header row.
- Write your schema in code, in a YAML or JSON file, with Pydantic classes, or by importing an OWL or RDFS ontology. Start from the default schema or a preset for operations or legal documents, then override or extend it.
- GLiNER reads every chunk on your machine and extracts entities and relations, so you can build a graph without an LLM key. In hybrid mode, an LLM re-reads eligible chunks, such as those with a kept entity scoring under 0.75, up to an escalation budget (20% of a batch by default).
- Items the models find that your schema does not allow are saved as candidates with links to their source passages. You can list, approve, or reject them, and an approval writes a schema patch for you to review.
- Entity resolution merges duplicates in tiers. Mentions with the same label and the same text share one entity. A fuzzy name score of 0.97 or more, or an embedding cosine similarity of 0.95 or more, makes a match, and the match is stored as a link between entities. Pairs with a cosine similarity from 0.80 to 0.95 are ambiguous. Clustering decides the tight groups, and an LLM reviews the rest, up to a limit you set for each label.
- A match is a link, so the original entities and their relations stay in the graph. You can preview a graph-wide cleanup before you apply it, re-check named entities, and turn off a single match.
- Adding the same folder again skips unchanged documents and replaces changed ones. Each document is written as one job, and nothing from a running job appears in search until it finishes.
- Soft delete removes a document from search and keeps its history. Purge removes every version.
- Community detection groups related entities and writes a report for each group, which `search_themes` uses to answer broad questions.

### Search, read, and cite evidence

Retrieval finds the parts of your documents that answer a question, and it lets an answer point back to the exact text it came from. No single search finds everything. A name lookup finds "Ada Lovelace" and misses "the main themes in this corpus". A lexical (full-text) search finds an exact contract term but not its paraphrase. A semantic (vector) search finds the paraphrase but can rank a similar wrong passage first. The same evidence tools run in Python, in the built-in agent, and on the MCP server.

> **[IMAGE: retrieval-flow]**
> Alt text: A query goes to passage search, or to entity search and then relationship exploration. Both return evidence ids. Fetch turns an id into its exact text. Document tree navigation moves from a passage to neighboring passages and returns more ids. The citation check compares cited ids with the ids that were fetched.
> Prompt: A left-to-right flow diagram on a light background. A "Query" box on the left splits into two paths. The top path goes to "Passage search" with three small chips for lexical, semantic, and hybrid. The bottom path goes to "Entity search" and then to "Explore relationships". Both paths output a stack of small "evidence id" tags. A "Fetch evidence" box turns an id into a block of exact passage text with a title and a "current" version label. A "Navigate document tree" box loops from a passage back to neighboring ids. On the far right, a "Check citations" box compares cited ids with fetched ids and outputs a numbered answer with a Sources list. Flat vector style, thin lines, two accent colors, 16:9 format.

#### From a question to a cited answer

The example question is "How soon is customer data erased?" over a short set of engineering notes. The output below comes from a real run of the [evidence tools](https://ontogr.github.io/agentic-graphrag/stable/guides/find-and-cite-evidence), and your ids will differ.

First, search returns the best matches as short previews. Each match has a score, an evidence id, the searches that found it, and the first characters of the passage.

```text
ok
0.0328  ev1:c:f24b301d...d7c4d6ef  ['lexical', 'semantic']
    Data retention  Robot logs are kept for 30 days and then deleted. A cu
0.0320  ev1:c:f24b301d...3e66aa77  ['lexical', 'semantic']
    Acme Robotics engineering notes  Route planning  Maria Chen works for
0.0161  ev1:c:f24b301d...12cd16fb  ['semantic']
    | Component | Owner | Purpose | | --- | --- | --- | | Orion Planner |
```

An evidence id names one passage in one version of one document, so it keeps pointing to the same text after the document changes. A preview can stop before the sentence you need, so the next step reads the whole passage.

Second, fetch returns the exact stored text for an id. The first line reports the fetch status (`ok` means the text is complete), the document version (`current` means the document has not changed since the id was made), and the title.

```text
ok current Acme Robotics engineering notes
Data retention

Robot logs are kept for 30 days and then deleted. A customer can ask Acme Robotics to erase their delivery data. After the request is verified, the data is deleted within 10 business days.
```

Third, the answer cites ids, and the citation check compares each cited id with the ids that were fetched. Here the answer cites three ids and only the first was read.

```text
ev1:c:f24b301d...d7c4d6ef    valid
ev1:c:f24b301d...12cd16fb    not_fetched
ev1:c:oops                   malformed
```

Valid ids become numbered references with a Sources list.

```text
Customer data is deleted within 10 business days. [1]

### Sources

[1] Acme Robotics engineering notes
```

#### Passage search

`search_evidence` runs over the chunks of the documents in scope. It sees only the current version of each document, and it skips chunks that an ingestion job is still writing.

| Mode | How it matches | Finds | Limit |
| --- | --- | --- | --- |
| `lexical` | Full-text index on chunk text. The query is reduced to plain lowercase words, and any word can match. | Exact words, identifiers, defined terms, and names. | Misses synonyms and paraphrases. Quotes, `AND`, and `-` have no effect. |
| `semantic` | Embeds the query and finds the chunks with the nearest embeddings. A chunk is embedded with its heading path in front, so a query can match a section title. | A passage that says the same thing in different words. | Always returns the nearest chunks, even when none answers the question. Needs the embedding model that ingestion used. |
| `hybrid` (default) | Runs both searches and fuses the two ranked lists with reciprocal rank fusion. | Everything either search finds, ranked higher when both rank it well. | Reports `partial` when one of the two searches fails. |

Reciprocal rank fusion adds `1 / (60 + r)` for a chunk at rank `r` in each list, and it ignores raw scores. When a cross-encoder reranker is available, hybrid search also reorders its top hits with it and marks the result `reranked`. A reranker that times out or fails leaves the fused order in place. With an external vector store, the store performs the dense and lexical fusion for hybrid mode, and `lexical` mode always searches the graph full-text index.

> **[IMAGE: hybrid-fusion]**
> Alt text: A lexical ranking and a semantic ranking of the same chunks are combined by reciprocal rank fusion into one ranking. A chunk that ranks well in both lists moves to the top.
> Prompt: A simple diagram of two short ranked lists side by side, one titled "Lexical" and one titled "Semantic", each with four chunk cards numbered by rank. Colored lines connect the same chunk across the two lists. On the right, a third list titled "Hybrid" shows the combined order, with the chunk that ranks well in both lists at the top and a small formula "1 / (60 + rank)" under the title. Flat vector style on a light background, 4:3 format.

#### Entity search and relationship exploration

`entity_search` finds the things your schema names, such as people, contracts, or products, by name or by meaning. It runs a lexical search over entity names and a semantic search over entity embeddings for each schema label, then fuses them. It returns an entity only when a visible passage in scope mentions it, and each hit lists up to three of those passages as evidence ids. An entity whose passages are all out of date comes back as `unsupported`.

`explore_relationships` follows the stored relations around one entity for up to two steps. It marks each edge as an `assertion`, when one or more visible passages state it, or as a `path`, when the graph connects two entities and no passage states the link. Assertion edges list the passages that state them, so you can fetch and cite them. The walk is bounded by node, edge, and depth limits, and `truncated_by` names the bound that cut it.

Entity search depends on extraction, so a fact that extraction missed has no entity. Passage search still finds that fact, because it reads the stored text.

#### Document tree navigation

A search hit is one chunk. The chunk can start mid-section, end inside a table, or hold an answer whose condition sits in the paragraph before it. `navigate_document_tree` follows the structure that ingestion recorded, starting from an evidence id.

| Relation | Returns |
| --- | --- |
| `parent` | The section that holds the passage, with its heading path. |
| `siblings` | The other sections under the same parent section. |
| `children` | The other passages under the same section or table, in reading order. |
| `previous`, `next` | The adjacent passage in reading order. |
| `table_context` | The table passage with the row passages before and after it. Every table passage repeats the header rows. |

Navigation reads only the document version of the starting passage, and it cannot search. Text it returns is not citable until `fetch_evidence` returns it in full.

#### Theme search

`search_themes` answers broad questions such as "what are the main themes in this corpus". It matches the query against the community reports from the last community detection run, and it returns each matching theme with its main entity names and the supporting passages as evidence ids. A theme returns no passages outside your scope, and documents added after the last run are left out until the next run.

#### Fetch evidence and check citations

`fetch_evidence` returns the exact stored text for evidence ids, with the title, the source, and the version status. Only a complete fetch makes an id citable, and a result reports when the text was truncated or covers only part of the range requested. An id from an earlier version of an updated document still returns its text, labeled `superseded`, so an old citation stays checkable.

`check_citations` returns one verdict for each cited id: `valid`, `not_fetched`, `unavailable` (the id names a document outside the scope), or `malformed`. The built-in agent runs it as a tool and again after its answer, and it gives the agent one repair pass when some ids fail. Numbered references replace the valid ids in the final answer.

#### Choose a tool

| The question | Start with | Then |
| --- | --- | --- |
| Contains an exact word, a code, a defined term, or a quoted phrase | `search_evidence` in `lexical` mode | Read the best hits with `fetch_evidence`. |
| Describes an idea in words the document may not use | `search_evidence` in `semantic` mode | Read the passages you will use with `fetch_evidence`. |
| Fits neither case, or you are unsure | `search_evidence` in `hybrid` mode | Read the hits you will quote with `fetch_evidence`. |
| Names a person, product, or clause and asks how it connects to other things | `entity_search` | `explore_relationships` from the best entity, then fetch the passages on its assertion edges. |
| Needs the section, the table, or the text around a passage you already have | `navigate_document_tree` from that passage's id | Fetch the neighbors you cite. |
| Asks for the main themes of a corpus | `search_themes` | Fetch and cite the supporting passages. |
| Has an answer that cites evidence | `check_citations` | Remove or fetch any id that fails. |

The [tools reference](https://ontogr.github.io/agentic-graphrag/latest/reference/tools) lists every parameter and limit, and [Retrieval](https://ontogr.github.io/agentic-graphrag/stable/concepts/retrieval) compares the strategies by mechanism and limit.

#### Rules that every evidence tool follows

- You choose which documents a caller may read. The scope sits outside the model, the tools apply it inside each query, and an id from a document outside the scope behaves as if the document does not exist.
- Every tool limits how many results and how much text it returns, and a result sets `truncated` when a limit cut it short.
- A failed search says so. If one half of a hybrid search fails, the status is `partial` and the result names the failed half. An empty list means that the search ran and found nothing.
- A score orders the matches of one call. Scores from different modes or different tools do not compare.
- An empty result means that no current passage matched the query. It does not prove that the answer is missing.

### Record conversation history and decision traces

> **[IMAGE: conversation-history]**
> Alt text: The agent records messages, tool calls, tool results, and named steps under a task. Decision traces cite document passages, task events, and earlier decisions. A source change flags affected decisions for review, and a later run can resume the task and search earlier decisions.
> Prompt: A diagram with a task card on the left that holds an ordered row of event chips (message, tool call, tool result) and a short list of named steps with state icons. On the right, three decision cards each show a conclusion and a rationale, with arrows to a document passage, to an event chip, and to another decision. A document card at the bottom shows a "new version" badge, and an arrow from it turns the cited decision cards amber with a "needs review" label. A second, fainter task card on the far left shows a later run resuming from the stored steps. Flat vector style on a light background, 16:9 format.

Conversation history

- A task has a goal, an ordered event log, and named steps. The event log holds messages, tool calls, tool results, and notes.
- A step is marked not started, in progress, completed, failed, or unknown.
- A resumed task starts from its goal, step counts, active decisions, and decisions that need review. The agent reuses completed steps and marks steps that were still running as unknown so it can run them again.
- A repeated request ID returns the saved result for a completed write. A failed multi-statement write on FalkorDB can leave partial effects. See the [retry limits](https://ontogr.github.io/agentic-graphrag/latest/guides/configure-storage-backends#retried-history-and-decision-writes).
- You can redact the body of one event or delete a whole task with its events and steps.

Decision traces

- A decision stores a conclusion, a concise rationale, assumptions, and open questions.
- Supports point to document passages, task events, or earlier decisions. A decision can cite only evidence that the same run or server session fetched in full.
- When a cited document gets a new version or is removed, the decision is flagged for review with the reason. Decisions that depend on a flagged decision are flagged too, in small batches, so an interrupted review can continue.
- A reviewer can reaffirm a decision after reading the current text, replace it with a new decision, or reject it. The earlier record and its support history stay.
- Agents can search earlier decisions in the same project and list choices that different tasks decided differently. The built-in agent's search leaves out decisions that need review, and the agent cannot cite one as support.

You can manage this state from Python without the built-in agent. `ConversationHistory` creates tasks, records events, and sets steps, and `DecisionTraces` records supported decisions and manages review.

```python
from agrag.history import ConversationHistory
from agrag.decisions import DecisionTraces
```

The [decision traces guide](https://ontogr.github.io/agentic-graphrag/latest/guides/decision-traces) records and reviews decisions end to end, and the [Python API reference](https://ontogr.github.io/agentic-graphrag/stable/api/) lists the complete contracts.

### Use the built-in agent or any MCP client

> **[IMAGE: full-flow]**
> Alt text: Documents are loaded, chunked, extracted, and resolved into a graph with enterprise knowledge, conversation history, and decision traces. A changed document flags the decisions that cite it. An agent searches and reads the graph, records its events and steps, and returns an answer with checked numbered sources.
> Prompt: A wide left-to-right pipeline diagram. On the left, document icons flow through four labeled stages: Load, Chunk, Extract, Resolve. The stages feed a central graph block drawn as three thin layers: knowledge, history, decisions. On the right, an agent box and an "MCP client" box both read from the graph through a small row of tool icons. The agent box outputs an answer card with numbered references [1] [2] and a Sources list. A small arrow from the document stage to the decisions layer is labeled "changed document flags decisions". Flat vector style on a light background, two accent colors, 16:9 format.

Built-in agent

- The agent is built for a fixed set of documents, a project, and an author, and it reads nothing else.
- It uses the same evidence tools as the MCP server and cites only passages it fetched in full.
- Citations are checked against passages read in the same run, and the agent gets one repair pass when some fail.
- Every run ends with a status: `answered`, `insufficient_evidence`, `partial`, or `budget_exhausted`, among others. You set how many steps and tool calls a run may use.
- Messages, tool calls, and tool results are saved to the task log as the run goes.
- Use one model, a fallback chain, or a rotation across Anthropic, OpenAI, OpenAI-compatible, and Google models.

MCP server

- `agrag-mcp` is a local server that talks to your MCP client over standard input and output.
- It offers the evidence tools and the conversation history and decision tools under the same names as the agent.
- It starts read-only and shows only the documents you list. Writing is switched on by the operator, and rejecting a decision has its own switch.
- Each result has a size limit and a deadline, and the server reports what it left out.
- A client can reuse a request identifier when it retries a write.

Operating the system

- Pass an OpenTelemetry tracer to the graph, the agent, the stores, the embedders, and the extractors. Spans cover loading, chunking, extraction, resolution, storage, search, and LLM calls. Without a tracer, nothing is recorded.
- Evaluation tools score answer correctness, faithfulness, context precision, context recall, and citation accuracy with a judge model that you choose. They also score extraction, duplicate groups, and agent runs on your own questions.
- Settings come from environment variables or a file, with a prefix for each area. The optional extras are `neo4j`, `falkordb`, `qdrant`, `milvus`, `weaviate`, `embed-local`, `extract`, `llm`, `agents`, `mcp`, `docling`, `observability`, `community`, `eval`, and `schema-formats`.

The [features page](https://ontogr.github.io/agentic-graphrag/stable/get-started/features) lists every capability with links to the guide for each.

### Choose where the graph and vectors live

Neo4j or FalkorDB stores the graph, the full-text indexes, and by default the vector indexes. Both support ingestion, entity resolution, hybrid search, community summaries, conversation history, and decision traces.

| Option | Install | Select in Python | Use it when |
| --- | --- | --- | --- |
| Neo4j 5.23+ | `uv pip install "agentic-graphrag[neo4j]"` | `build_graph_store("neo4j")` | You use Neo4j or Aura, or need rollback across multi-statement writes. |
| FalkorDB 4.22.2+ | `uv pip install "agentic-graphrag[falkordb]"` | `build_graph_store("falkordb")` | You want a Redis-protocol graph server and can account for partial writes without multi-statement rollback. |

Vectors can instead live exclusively in Qdrant, Milvus, or Weaviate. Install the `qdrant`, `milvus`, or `weaviate` extra beside the graph driver, and pass the matching `QdrantVectorStore`, `MilvusVectorStore`, or `WeaviateVectorStore` to ingestion and retrieval. The graph database still holds documents, relations, provenance, and the full-text indexes. One placement covers chunks, entities, resolved entities, and communities for the life of a graph, so changing it needs a new graph and a new ingestion. Use a separate collection prefix for each graph. For MCP, set `MCP_GRAPH_STORE` to `neo4j` or `falkordb` and `MCP_VECTOR_STORE` to `qdrant`, `milvus`, or `weaviate`.

[Configure storage backends](https://ontogr.github.io/agentic-graphrag/stable/guides/configure-storage-backends) has server commands and connection settings, [Choose where vectors live](https://ontogr.github.io/agentic-graphrag/latest/guides/choose-where-vectors-live) covers the external stores, and [Graph storage](https://ontogr.github.io/agentic-graphrag/stable/concepts/graph-storage) compares search and transaction behavior.

## Quickstart

In this example you add one document, ask a question about it, and get an answer with numbered sources. You need Python 3.11 or newer, a running Neo4j database, and an OpenAI-compatible LLM endpoint.

### 1. Start Neo4j

Start a local database with Docker, or use [Neo4j Aura](https://neo4j.com/cloud/platform/aura-graph-database/). The password in the command must match the one you set in step 3.

```bash
docker run -d --name agrag-neo4j -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-neo4j-password neo4j:5.26.0-community
```

### 2. Install

Install the package from PyPI into a fresh virtual environment:

```bash
uv venv
source .venv/bin/activate
uv pip install "agentic-graphrag[neo4j,extract,agents]" --torch-backend=auto
```

See [Installation](https://ontogr.github.io/agentic-graphrag/stable/get-started/installation) for other package managers and the optional parts you can add.

### 3. Add your settings

Create a file named `.env` in the folder where you will run the example. Replace the values with your own, and keep the file out of version control.

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password
AGENT_LLM_BASE_URL=https://your-endpoint.example.com/v1
AGENT_LLM_API_KEY=your-api-key
AGENT_LLM_MODEL_ID=your-model-id
```

The last three lines are the address, key, and model of your OpenAI-compatible LLM endpoint. For a Neo4j database on another machine, see [Configuration](https://ontogr.github.io/agentic-graphrag/stable/reference/configuration).

### 4. Run the example

Put any Markdown or text file in the same folder and name it `your-document.md`. Save the following as `example.py` and run `python example.py`. The first run downloads the embedding and extraction models, so it takes longer than later runs.

```python
import asyncio
from pathlib import Path

from agrag.agents import AgentLLMSettings, build_agent
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import ExtractionSettings, Graph

# Any Markdown or text file you have.
DOCUMENT = Path("your-document.md").resolve()


async def main() -> None:
    # Connect to the database and load the model that turns text into vectors.
    store = build_graph_store("neo4j")
    embedder = build_embedder("ibm-granite/granite-embedding-small-english-r2")
    try:
        # Read the document into the graph. This step runs on your machine.
        # "operations" is a preset schema, and max_llm_pairs=0 sends no
        # duplicate-matching pairs to an LLM.
        graph = await Graph.open(
            schema="operations",
            graph_store=store,
            embedder=embedder,
            extraction_settings=ExtractionSettings(mode="gliner"),
            max_llm_pairs=0,
        )
        await graph.add(DOCUMENT)

        # Create an agent that may read only this document.
        agent = build_agent(
            graph_store=store,
            embedder=embedder,
            scope=frozenset({str(DOCUMENT)}),
            project_id="my-project",
            agent_id="researcher",
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
        )

        # Ask a question about the document.
        result = await agent.ainvoke({
            "task_name": "first-question",
            "question": "What are the main points of this document? Cite your sources.",
        })
        print(result["answer"])
    finally:
        await store.close()


asyncio.run(main())
```

The script prints an answer that ends with a numbered list of sources. Run it again with the same task name and the agent continues where it stopped.

> **[IMAGE: quickstart-output]**
> Alt text: A terminal showing the answer from the quickstart script, with numbered references in the text and a Sources list at the end.
> Prompt: A realistic dark terminal window showing the printed output of a Python script. Three short paragraphs of answer text contain bracketed references [1], [2], and [3]. Under a "Sources" heading, a numbered list shows the same document title three times with different section names. Monospace font, subtle window chrome, no logos, 16:9 format.

To run the example on FalkorDB, follow the [FalkorDB setup](https://ontogr.github.io/agentic-graphrag/latest/guides/configure-storage-backends#set-up-a-falkordb-graph-store), replace the `neo4j` install extra with `falkordb`, use `FALKORDB_*` connection settings, and change the store selection to `build_graph_store("falkordb")`.

### Next steps

- [Find and cite evidence](https://ontogr.github.io/agentic-graphrag/stable/guides/find-and-cite-evidence) searches passages and checks citations from Python.
- [Decision traces](https://ontogr.github.io/agentic-graphrag/latest/guides/decision-traces) records supported decisions and reviews them when sources change.
- [Define a graph schema](https://ontogr.github.io/agentic-graphrag/stable/guides/define-a-graph-schema) describes your own entities and relations.

## Use MCP

Run `agrag-mcp` to give an MCP client tools that search your documents, read exact passages, check citations, and access conversation history and decision traces.

Install the server in the same virtual environment as before:

```bash
uv pip install "agentic-graphrag[neo4j,mcp]"
```

The server must read the graph that you built with ingestion, with the same embedding model. Set `EMBEDDING_MODEL` to the model you used for ingestion if you changed the default. Then add the server to your MCP client. Replace the document path with the full path of a file you added to the graph. It must equal the path that ingestion stored, which is the value of `str(DOCUMENT)` in the quickstart.

```json
{
  "mcpServers": {
    "agrag": {
      "command": "agrag-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your-neo4j-password",
        "MCP_SCOPE_DOCUMENT_KEYS": "/full/path/to/your-document.md",
        "MCP_PROJECT_ID": "my-project",
        "MCP_AGENT_ID": "researcher"
      }
    }
  }
}
```

If your client cannot find `agrag-mcp`, use its full path inside the virtual environment, for example `/full/path/to/.venv/bin/agrag-mcp`. The server starts read-only and reads only the documents you list. The project and agent IDs enable history and decision tools, but writes remain disabled until you change the server settings. See the [MCP server guide](https://ontogr.github.io/agentic-graphrag/stable/guides/run-the-mcp-server) for the other settings.

For FalkorDB, install `agentic-graphrag[falkordb,mcp]` instead. In the client configuration, replace the `NEO4J_*` entries with `"MCP_GRAPH_STORE": "falkordb"`, `"FALKORDB_URL": "redis://localhost:6379"`, and `"FALKORDB_GRAPH": "agrag"`.

## Examples

- [Company briefing](examples/company_briefing/README.md) uses an annual report as source material. It records task events and steps, saves decisions with explicit document supports, and flags a decision for review when a correction changes the text it cites.
- [Connected context](examples/connected_context/workflow.py) connects knowledge, conversation history, and decision traces in one workflow.

## Contributing

We welcome bug fixes, new features, documentation improvements, and other contributions. Please read our [Contributing guide](CONTRIBUTING.md) before submitting a pull request.

## Acknowledgements

Agentic GraphRAG builds on the work behind these projects and papers.

- [Graphiti](https://github.com/getzep/graphiti) for layered graph search and entity-aware retrieval
- [Cognee](https://github.com/topoteretes/cognee) for data pipelines, graph memory, and consolidation
- [FalkorDB GraphRAG SDK](https://github.com/FalkorDB/GraphRAG-SDK) for graph-native retrieval and entity resolution
- [Neo4j GraphRAG](https://github.com/neo4j/neo4j-graphrag-python) for Neo4j retrieval and vector integration
- [GLiNER](https://arxiv.org/abs/2311.08526) for generalist zero-shot information extraction
- [BAML](https://boundaryml.com/), [Docling](https://github.com/docling-project/docling), and [Chonkie](https://github.com/chonkie-inc/chonkie) for typed LLM calls, document parsing, and chunk splitting

## License

Agentic GraphRAG is licensed under the [Apache License 2.0](https://github.com/ontogr/agentic-graphrag/blob/main/LICENSE).
