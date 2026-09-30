<h1 align="center">Agentic GraphRAG</h1>

<p align="center"><strong>Build a knowledge graph from your documents. Get answers that cite their evidence.</strong></p>

<p align="center">
<a href="https://pypi.org/project/agentic-graphrag/"><img src="https://img.shields.io/pypi/v/agentic-graphrag.svg" alt="PyPI"></a>
<a href="https://pypi.org/project/agentic-graphrag/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
<a href="https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=CI&logo=githubactions" alt="CI"></a>
<a href="https://codecov.io/gh/ontogr/agentic-graphrag"><img src="https://codecov.io/gh/ontogr/agentic-graphrag/branch/main/graph/badge.svg" alt="Codecov"></a>
<a href="https://ontogr.github.io/agentic-graphrag/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=readthedocs" alt="Docs"></a>
<a href="LICENSE"><img src="https://img.shields.io/github/license/ontogr/agentic-graphrag?color=green" alt="Apache-2.0 license"></a>
</p>

<p align="center">
<a href="https://ontogr.github.io/agentic-graphrag/get-started/quickstart">Quickstart</a> ·
<a href="https://ontogr.github.io/agentic-graphrag/concepts/architecture">Concepts</a> ·
<a href="https://ontogr.github.io/agentic-graphrag/guides/ingest-documents">Guides</a> ·
<a href="https://ontogr.github.io/agentic-graphrag/api">API reference</a>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/readme/pipeline.png" alt="Agentic GraphRAG pipeline. Sources are loaded, chunked, extracted, and resolved into a Neo4j graph and optional vector stores. Retrieval feeds a planner, researcher, and verifier agent that returns a cited answer. OpenTelemetry traces every layer." width="900"></p>

Agentic GraphRAG (`agrag`) reads your files, extracts the people, places, and things in them, and links those facts in a graph. An agent then answers your questions from that graph. It checks its own evidence, and it cites a source for every claim.

A plain vector search finds passages that look like your question. It cannot join a fact in one document to a fact in another. A graph can. "Who founded the company that Satya Nadella works at?" needs two facts from two places. The graph joins them.

## What you get

- **Your schema, not a fixed one.** You name the entity types, the relation types, and the pairs each relation can join. Nothing outside the schema enters the graph.
- **No LLM needed to build the graph.** A local GLiNER model reads every chunk. An LLM reads only the chunks where the local model is weak, and only if you turn it on.
- **Duplicates handled with care.** Four tiers compare mentions: exact, fuzzy, embedding, and LLM. A pair that is not clearly the same stays apart. Matches are stored as edges, so no original entity is lost.
- **Many ways to search.** Entity, chunk, community, text-to-Cypher, and graph-walk search run together. Reciprocal rank fusion and reranking order the results.
- **Answers you can check.** A planner, a researcher, and a verifier work in a loop. Every claim carries a key that points to the stored evidence.
- **Your choice of stores.** Neo4j holds the graph and its vector index. Qdrant, Weaviate, and Milvus add dense and hybrid search.
- **Built to run in production.** OpenTelemetry traces every stage, errors follow a policy you set, and documents can be updated and deleted.

## See it work

You need Python 3.11 or newer and a Neo4j database, version 5.23 or newer. The free [Neo4j Aura](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) tier works. The full [Quickstart](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) shows the Aura setup step by step.

```bash
uv venv && source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu   # skip on a GPU machine
uv pip install "agentic-graphrag[neo4j,extract,embed-local,agents]"
```

Save your Aura credentials as `.env` in the working directory. It sets `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.

**Step 1. Build the graph.** Save this script as `build_graph.py`. It needs no LLM key.

```python
import asyncio

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import Graph
from agrag.ingestion.extract import GlinerExtractor

schema = GraphSchema(
    name="company-facts",
    version="1",
    entities=[
        EntityType(label="Person", description="A named individual."),
        EntityType(label="Organization", description="A company or institution."),
        EntityType(label="Location", description="A city or country."),
    ],
    relations=[
        RelationType(
            label="FOUNDED",
            description="A person founded an organization.",
            patterns=[("Person", "Organization")],
        ),
        RelationType(
            label="WORKS_AT",
            description="A person works at an organization.",
            patterns=[("Person", "Organization")],
        ),
        RelationType(
            label="HEADQUARTERED_IN",
            description="An organization has its headquarters in a location.",
            patterns=[("Organization", "Location")],
        ),
    ],
)

TEXT = (
    "Satya Nadella works at Microsoft. Bill Gates founded Microsoft. "
    "Microsoft is headquartered in Redmond."
)


async def main() -> None:
    graph_store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=schema,
        graph_store=graph_store,
        embedder=build_embedder("ibm-granite/granite-embedding-small-english-r2"),
        extractor=GlinerExtractor(),
    )
    try:
        result = await graph.add(text=TEXT, return_chunks=True)
        print("documents:", result.ingestion.documents)
        print("chunks:", len(result.chunks))
        print("entities extracted:", result.extraction.entities_extracted)
        print("relations extracted:", result.extraction.relations_extracted)
    finally:
        await graph_store.close()


if __name__ == "__main__":
    asyncio.run(main())
```

```text
documents: 1
chunks: 1
entities extracted: 6
relations extracted: 3
```

The first run downloads two models, about 385 MB in total.

**Step 2. Ask a question.** This step needs an OpenAI-compatible LLM endpoint. Add `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` to `.env`, then save this script as `ask.py`:

```python
import asyncio

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval import SearchEngine

from build_graph import schema

QUESTION = "Who founded the company that Satya Nadella works at?"


async def main() -> None:
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        engine = SearchEngine(
            graph_store=graph_store,
            embedder=build_embedder("ibm-granite/granite-embedding-small-english-r2"),
            graph_schema=schema,
        )
        agent = build_agent(
            engine=engine,
            llm_settings=AgentLLMSettings.from_openai_compatible_env(),
            graph_schema=schema,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": QUESTION}]}
        )
        answer = result["messages"][-1]
        print(answer["content"] if isinstance(answer, dict) else answer.content)
        print("evidence keys:", ", ".join(result["ledger"].keys))
    finally:
        await graph_store.close()


asyncio.run(main())
```

```bash
BAML_LOG=off python ask.py
```

The answer varies with your model. This is an example:

```text
Satya Nadella works at Microsoft (E1, E3), which was founded by Bill Gates (E2, E3, C1).
evidence keys: E1, E2, E3, E4, C1, V1
```

The agent needed two facts from two sentences. It joined them through the `Microsoft` node. Each key in brackets points to the stored evidence: `E` for an entity, `C` for a chunk of source text, `V` for a value from a graph query.

## How it works

Ingestion builds the graph. Querying reads it. The same schema guards both.

### Load and chunk

A loader turns each source into documents. `agrag` picks the loader from the file extension, reads the text, detects the encoding, and gives each document a stable identity from its content. A chunker then splits each document. Every chunk keeps its place in the source, such as a character range, a heading path, or a page and box. An answer can point to the exact spot.

| Format | Extensions | Needs |
| --- | --- | --- |
| Text and Markdown | `.txt` `.log` `.md` `.markdown` | core |
| HTML | `.html` `.htm` | core |
| Tables and records | `.csv` `.tsv` `.json` `.jsonl` `.ndjson` | core |
| PDF, Word, PowerPoint, XML | `.pdf` `.docx` `.pptx` `.xml` | `docling` extra |
| Images | `.png` `.jpg` `.jpeg` `.tif` `.tiff` `.bmp` | `docling` extra |
| AsciiDoc | `.adoc` `.asciidoc` | core (Docling reads it when installed) |

Ten chunkers cover recursive, token, sentence, heading, chat-turn, parent and child, Docling layout, semantic, neural, and code splitting. Rules pick a chunker for each document by loader, format, family, or URI. When one source fails, an error policy decides what happens. The policy applies to each source, so one bad file does not stop the rest.

```python
from agrag.loaders import ErrorPolicy

result = await graph.add(source="corpus/", error_policy=ErrorPolicy.QUARANTINE)

for failure in result.ingestion.quarantined_items:
    print(failure.item_id, failure.error_message)
```

`RAISE` stops the run, `SKIP` drops the source and counts it, and `QUARANTINE` sets it aside with the reason.

### Extract with your schema

The extractor reads one chunk at a time. It returns mentions and relations that match your schema. Validation removes any label, relation, or property that the schema does not declare.

The default path is local. GLiNER 2.5 runs in your process. It needs no API key, and it does not send your text anywhere. The escalating extractor adds an LLM as a fallback. The LLM reads a chunk only when the local model finds nothing in a chunk of eight words or more, or when its mean confidence is below 0.5.

```python
from agrag.ingestion import BAMLExtractor, EscalatingExtractor, GlinerExtractor

extractor = EscalatingExtractor(
    primary=GlinerExtractor(),
    escalate_to=BAMLExtractor(),
)
```

BAML gives the LLM a typed function built from your schema, so the model can return only declared labels. You can route calls across providers with a retry policy and a fallback list. Use an LLM for chunks where you need property values, because the local model reports spans and labels only.

### Resolve duplicates without losing data

One thing has many names: "Charles Babbage", "Babbage Charles", "C. Babbage". A graph with three nodes splits the evidence. A wrong merge is worse, because it mixes the facts of two things. For that reason every tier prefers "no match" when it is not sure.

<p align="center"><img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/readme/resolution.png" alt="Entity resolution tiers. A pair of mentions with the same label passes an exact tier, a fuzzy tier, an embedding tier, and an LLM tier. An unsure pair is never matched. A match writes a MATCHES edge and a derived ResolvedEntity, and the original entities stay." width="900"></p>

Only mentions with the same label are compared, so a city and a company with the same name stay apart. The exact tier merges two mentions with equal text after trimming and case folding. Every other match is stored as a `MATCHES` edge with its tier, score, and reason. `agrag` then derives one `ResolvedEntity` from each group of linked entities and links each member to it with `RESOLVED_AS`. Nothing is rewritten or deleted, so a later run can undo a decision.

`Graph.consolidate()` runs the same tiers over the whole graph. It is a dry run until you pass `apply=True`.

```python
report = await graph.consolidate()             # dry run: lists the matches it would write
report = await graph.consolidate(apply=True)   # writes MATCHES edges and ResolvedEntity nodes
```

### Keep the graph current

`Graph.update` replaces a document that changed. An unchanged document is a no-op. `Graph.delete_document` removes a document from search and prunes entities that lose their last evidence. Both work on a document key, and each runs as one job, so a crash leaves the document whole.

```python
await graph.update("notes/q3.md", text=new_text)
await graph.delete_document("notes/q3.md")
```

### Find themes with communities

Some questions have no single chunk as an answer, such as "What are the main themes in this corpus?" A community is a group of entities that many relations connect. `Graph.detect_communities` runs hierarchical Leiden clustering and keeps the broadest groups. It writes a title, a summary, a rating, and findings for each community. An LLM writes the report for a group with enough evidence. A small group gets a simple report with no LLM call. Search can then return a report instead of a list of low-level edges.

```python
report = await graph.detect_communities(apply=True)
```

### Store in Neo4j, add a vector store if you want one

Neo4j holds the whole graph and has a native vector index, which is enough for dense search and means one service to run. A dedicated vector store adds keyword search and a weighted blend of the two.

| Store | Dense search | Hybrid search | Runs |
| --- | --- | --- | --- |
| Neo4j | Native vector index | No | Local or Aura |
| Qdrant | Yes | Dense and BM25, blended by weight | Local or cloud |
| Weaviate | Yes | Native | Local or cloud |
| Milvus and Zilliz | Yes | Native BM25 | Local or cloud |

`Graph.open` checks that your embedder matches the stored vector dimensions, and it raises an error on a mismatch.

### Retrieve with several methods at once

Graph data answers questions in different ways. A fact can sit in a source passage, on an entity, in a relation, or in a summary of a whole topic. No single search finds all four. A recipe picks the methods for a query, and the engine runs them at the same time. If one method fails, the others still return results.

| Recipe | Methods | Extra steps |
| --- | --- | --- |
| `ENTITY` | entity | none |
| `CHUNK` | chunk | none |
| `HYBRID` | entity, chunk | none |
| `HYBRID_RERANKED` | entity, chunk | community reports, cross-encoder rerank |
| `GRAPH_EXPAND` | entity | graph walk, community reports |
| `THEMATIC` | community | none |
| `TEXT2CYPHER` | text2cypher | none |

Reciprocal rank fusion merges the ranked lists, so no method's score scale takes over. A recipe can then walk outward from the entity hits, add overlapping community reports, and rerank with a cross-encoder or by graph distance. A recipe is plain data, so you can read it and copy it.

```python
from agrag.retrieval import HYBRID, SearchEngine

engine = SearchEngine(graph_store=graph_store, embedder=embedder, graph_schema=schema)
results = await engine.search("What treats headaches?", HYBRID)
```

### Answer with an agent that checks itself

<p align="center"><img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/readme/agent-loop.png" alt="Agent loop. A planner splits the question into sub-questions. A researcher searches the graph. A verifier returns PASS, INSUFFICIENT, or CONTRADICTORY. INSUFFICIENT sends the gaps back to the researcher. The answer carries citation keys." width="900"></p>

A planner splits the question into two to four sub-questions. A researcher searches the graph with its tools and reports findings with citation keys. A verifier checks each sub-question alone and returns one verdict.

| Verdict | Meaning | Next step |
| --- | --- | --- |
| `PASS` | Every sub-question has support. Nothing conflicts. | The planner writes the answer. |
| `INSUFFICIENT` | A sub-question lacks evidence, or a claim does not match its evidence. | The planner sends the gaps back to the researcher, up to three times. |
| `CONTRADICTORY` | Two cited pieces of evidence conflict. | The planner states the conflict in the answer. |

The verifier has no tools, so it judges only the evidence in front of it. Each run keeps a ledger that maps every key (`E` entity, `R` relation, `C` chunk, `G` community report, `V` query value) to its stored evidence. You can limit every search to one document or tenant, and the model cannot step outside that scope.

### Trace every step

`agrag` records what it does as OpenTelemetry traces. You pass the tracer, and `agrag` never installs a global one. A trace shows each load, chunk, extraction, model call, resolution, storage write, search, and agent turn, with its timing. Any tool that reads OpenTelemetry can show it. Failures in `AddResult` carry a trace id, so you can find the full record.

### Score your own answers

`agrag.eval` holds metrics that score answers, retrieval, extraction, resolution, and agent runs on your documents and questions. See [Score agrag on your questions](https://ontogr.github.io/agentic-graphrag/guides/score-agrag-on-your-questions).

## The graph model

One typed property graph holds the sources, the knowledge, and the summaries. You can walk from any answer back to its source.

```text
(:Document)-[:PART_OF]->(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONED_IN]->(entity)
(entity)-[:<RELATION_TYPE>]->(entity)
(entity)-[:MATCHES]->(entity)
(entity)-[:RESOLVED_AS]->(:ResolvedEntity)
(entity)-[:MEMBER_OF]->(:Community)
```

An entity node carries its schema type as a label, for example `:Person`. A community node holds its report. See [Knowledge graph](https://ontogr.github.io/agentic-graphrag/concepts/knowledge-graph).

## Learn more

- **Start:** [Introduction](https://ontogr.github.io/agentic-graphrag/get-started/introduction) · [Installation](https://ontogr.github.io/agentic-graphrag/get-started/installation) · [Quickstart](https://ontogr.github.io/agentic-graphrag/get-started/quickstart)
- **Concepts:** [Architecture](https://ontogr.github.io/agentic-graphrag/concepts/architecture) · [Knowledge graph](https://ontogr.github.io/agentic-graphrag/concepts/knowledge-graph) · [Ingestion](https://ontogr.github.io/agentic-graphrag/concepts/ingestion) · [Loading](https://ontogr.github.io/agentic-graphrag/concepts/loading) · [Chunking](https://ontogr.github.io/agentic-graphrag/concepts/chunking) · [Extraction](https://ontogr.github.io/agentic-graphrag/concepts/extraction) · [Entity resolution](https://ontogr.github.io/agentic-graphrag/concepts/resolution) · [Resolved entities](https://ontogr.github.io/agentic-graphrag/concepts/resolved-entities) · [Communities](https://ontogr.github.io/agentic-graphrag/concepts/communities) · [Agent loop](https://ontogr.github.io/agentic-graphrag/concepts/agent-loop) · [Retrieval](https://ontogr.github.io/agentic-graphrag/concepts/retrieval) · [Graph storage](https://ontogr.github.io/agentic-graphrag/concepts/graph-storage) · [Observability](https://ontogr.github.io/agentic-graphrag/concepts/observability)
- **Guides:** [Ingest documents](https://ontogr.github.io/agentic-graphrag/guides/ingest-documents) · [Update and delete documents](https://ontogr.github.io/agentic-graphrag/guides/update-and-delete-documents) · [Define a graph schema](https://ontogr.github.io/agentic-graphrag/guides/define-a-graph-schema) · [Configure chunking](https://ontogr.github.io/agentic-graphrag/guides/configure-chunking) · [Extract and resolve](https://ontogr.github.io/agentic-graphrag/guides/extract-and-resolve) · [Consolidate duplicates](https://ontogr.github.io/agentic-graphrag/guides/consolidate-duplicates) · [Detect communities](https://ontogr.github.io/agentic-graphrag/guides/detect-communities) · [Configure storage backends](https://ontogr.github.io/agentic-graphrag/guides/configure-storage-backends) · [Retrieve and answer](https://ontogr.github.io/agentic-graphrag/guides/retrieve-and-answer) · [Trace an agent run](https://ontogr.github.io/agentic-graphrag/guides/trace-an-agent-run) · [Score on your questions](https://ontogr.github.io/agentic-graphrag/guides/score-agrag-on-your-questions) · [Troubleshoot common errors](https://ontogr.github.io/agentic-graphrag/guides/troubleshoot-common-errors)
- **Reference:** [Core API](https://ontogr.github.io/agentic-graphrag/api) · [Configuration](https://ontogr.github.io/agentic-graphrag/reference/configuration) · [Trace spans](https://ontogr.github.io/agentic-graphrag/reference/trace-spans)

<details>
<summary>Extras</summary>

| Extra | Adds |
| --- | --- |
| `neo4j` | The Neo4j graph store and its native vector index |
| `embed-local` | Sentence Transformers embeddings that run on your machine |
| `extract` | GLiNER 2.5 extraction that runs on your machine |
| `llm` | BAML extraction and match verification with an LLM |
| `agents` | The LangGraph runtime for the question-answering agent |
| `docling` | PDF, Word, PowerPoint, image, and XML parsing, and layout-aware chunking |
| `qdrant`, `weaviate`, `milvus` | The Qdrant (with BM25 sparse embeddings), Weaviate, and Milvus or Zilliz vector stores |
| `observability` | The OpenTelemetry SDK and OTLP exporter |
| `community` | Leiden community detection |
| `eval` | The DeepEval and AgentEvals metrics in `agrag.eval` |
| `chunk-semantic`, `chunk-neural`, `chunk-code` | The semantic, neural, and code chunkers |

</details>

<details>
<summary>Project structure</summary>

```text
agrag/
├── loaders/ chunking/              read files, split into chunks
├── ingestion/ common/ cypher/      Graph API and pipeline, data models, Cypher builders
├── graphdb/ vectordb/ embedding/   stores and embedders
├── retrieval/ agents/              search and the question-answering agent
└── eval/ llm/ observability.py     metrics, BAML sources and client, OpenTelemetry helpers
```

</details>

<details>
<summary>References</summary>

- **Ideas:** [Microsoft GraphRAG](https://arxiv.org/abs/2404.16130) (communities and reports), [Graphiti](https://github.com/getzep/graphiti) (layered graph search), [Cognee](https://github.com/topoteretes/cognee) (graph memory pipelines), [KG-Gen](https://github.com/stair-lab/kg-gen) (alias deduplication), [PathRAG](https://github.com/BUPT-GAMMA/PathRAG) (relational-path retrieval).
- **Building blocks:** [GLiNER](https://arxiv.org/abs/2311.08526), [BAML](https://boundaryml.com/), [Docling](https://github.com/docling-project/docling), [Chonkie](https://github.com/chonkie-inc/chonkie), [Sentence Transformers](https://www.sbert.net/), [FastEmbed](https://github.com/qdrant/fastembed), [OpenTelemetry](https://opentelemetry.io/), [Neo4j](https://neo4j.com/), [Qdrant](https://qdrant.tech/), [Weaviate](https://weaviate.io/), and [Milvus](https://github.com/milvus-io/milvus).

</details>

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and pull request rules. Report a problem in [Issues](https://github.com/ontogr/agentic-graphrag/issues). Apache License 2.0: see [LICENSE](LICENSE).
