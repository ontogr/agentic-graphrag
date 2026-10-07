<h1 align="center"><a href="https://github.com/ontogr/agentic-graphrag">Agentic GraphRAG</a></h1>

<div align="center">

[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ontogr/agentic-graphrag)
[![CI](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=CI&logo=githubactions)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=Ruff&logo=ruff)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml)
[![ty](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=ty&logo=python)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml)
[![Unit tests](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=unit%20tests&logo=pytest)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml)
[![Integration tests](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/integration.yml?branch=main&label=integration%20tests&logo=pytest)](https://github.com/ontogr/agentic-graphrag/actions/workflows/integration.yml)
[![Codecov](https://codecov.io/gh/ontogr/agentic-graphrag/branch/main/graph/badge.svg)](https://codecov.io/gh/ontogr/agentic-graphrag)
[![PyPI](https://img.shields.io/pypi/v/agentic-graphrag.svg)](https://pypi.org/project/agentic-graphrag/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/agentic-graphrag/)
[![Downloads](https://static.pepy.tech/badge/agentic-graphrag/month)](https://pepy.tech/project/agentic-graphrag)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=readthedocs)](https://ontogr.github.io/agentic-graphrag/)
[![License](https://img.shields.io/github/license/ontogr/agentic-graphrag?color=green)](LICENSE)

[Documentation](https://ontogr.github.io/agentic-graphrag/) · [Quickstart](#quickstart) · [Concepts](https://ontogr.github.io/agentic-graphrag/concepts/architecture) · [Guides](https://ontogr.github.io/agentic-graphrag/guides/ingest-documents) · [API reference](https://ontogr.github.io/agentic-graphrag/api)

</div>

Agentic GraphRAG is a modular, schema-driven system. It builds knowledge graphs from unstructured and structured data. A knowledge graph links typed entities with relations. It retrieves evidence across graph and vector indexes. It answers questions with agentic reasoning and cites its evidence.

A plain vector search finds passages that look like your question. It cannot join a fact in one document to a fact in another. "Who founded the company that Satya Nadella works at?" needs two facts from two places. A graph joins them.

<p align="center">
  <img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/readme/pipeline.png" alt="Agentic GraphRAG pipeline. Sources are loaded, chunked, extracted, and resolved into a Neo4j graph and optional vector stores. Retrieval feeds a planner, researcher, and verifier agent that returns a cited answer. OpenTelemetry traces every layer." width="900">
</p>

- One ingestion API for raw text, files, directories, globs, and prebuilt documents.
- Structure-aware loading and chunking with core text readers, Docling for rich documents, and Chonkie for text chunking.
- Schema-driven extraction with runtime-defined entity types, relation types, and valid graph patterns.
- Local-first extraction cascade using GLiNER 2.5 with type-safe BAML/LLM fallback for weak or ambiguous chunks. You need no LLM key to build a graph.
- Tiered entity resolution combining exact, fuzzy, embedding, and LLM-verified matching. An unsure comparison never matches.
- Non-destructive matching. Fuzzy, embedding, and LLM matches write `MATCHES` edges and a derived `ResolvedEntity`. The original entities and their provenance stay in the graph.
- Pluggable storage with Neo4j for graph data and native vectors, plus Qdrant, Weaviate, and Milvus/Zilliz for dedicated vector search.
- Layered retrieval across entities, chunks, community reports, graph neighborhoods, and generated Cypher, with hybrid fusion and reranking.
- Agentic plan-research-verify loop that decomposes questions, gathers evidence, checks it, and produces cited answers.
- OpenTelemetry-native observability across loading, chunking, extraction, resolution, storage, retrieval, and agent turns.

The system uses:

- [Docling](https://github.com/docling-project/docling) and [Chonkie](https://github.com/chonkie-inc/chonkie) for document parsing and chunking.
- [GLiNER 2.5](https://github.com/urchade/GLiNER) for local schema-guided entity and relation extraction.
- [BAML](https://boundaryml.com/) for typed LLM functions and provider-independent client routing.
- [Neo4j](https://neo4j.com/) for the property graph and optional native vector search.
- [Qdrant](https://qdrant.tech/), [Weaviate](https://weaviate.io/), and [Milvus](https://milvus.io/) for dense and hybrid retrieval.
- [Sentence Transformers](https://www.sbert.net/) and [FastEmbed](https://github.com/qdrant/fastembed) for dense and sparse embeddings.
- [OpenTelemetry](https://opentelemetry.io/) for vendor-neutral traces and metrics.

## Knowledge Graph

Agentic GraphRAG stores source material, extracted knowledge, and graph summaries in one typed property graph:

```text
(:Chunk)-[:PART_OF]->(:Document)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONED_IN]->(entity)
(entity)-[:<RELATION_TYPE>]->(entity)
(entity)-[:MATCHES]->(entity)
(entity)-[:RESOLVED_AS]->(:ResolvedEntity)
(entity)-[:MEMBER_OF]->(:Community)
```

An entity node carries its schema type as a label, for example `:Person`. You can walk from any answer back to its source document.

### Documents and chunks

Documents keep their source URI, format, loader, content hash, and record identity. Text formats use content-based identities. Binary Docling formats use raw-byte hashes. Chunks keep stable document links and source provenance:

- Text chunks record character and line spans plus their heading path.
- Layout-aware chunks record page numbers and bounding boxes.
- Record formats such as CSV, TSV, JSON, and JSON Lines preserve row identity.

### Entities and relations

Extraction produces mentions first, not graph nodes. Each mention keeps its source chunk, label, text span, confidence, and extractor provenance. Resolution then decides which mentions name the same thing. Mentions with the same label and the same normalized text share one entity node.

Relations are directed subject–predicate–object triples. The active schema constrains valid source type, relation type, and target type combinations. Validation removes invalid triples before they reach the graph.

### Matches and resolved entities

A fuzzy, embedding, or LLM match does not rewrite or delete anything. It writes a `MATCHES` edge with its tier, score, and reason. Agentic GraphRAG then derives one `ResolvedEntity` for each group of linked entities and links each member to it with `RESOLVED_AS`. A later run can undo a decision, because the original entities are still there. Retrieval can search resolved entities.

### Communities

Leiden clustering groups related entities into communities. `Graph.detect_communities` keeps the broadest groups of two or more entities. A group with enough supporting relations gets an LLM-written report with a title, summary, findings, and a rating from 0 to 10. A smaller group gets a simple report with no LLM call. Community reports provide broad context without forcing retrieval to return every low-level edge.

### Runtime schemas

`GraphSchema` is a first-class runtime value. It defines:

- entity types and their descriptions.
- relation types and their descriptions.
- valid `(source, relation, target)` patterns.
- the vocabulary injected into local and LLM extractors.

Use the `GENERIC` preset for open-domain data or provide a schema for a specific domain. The same schema guides extraction, validation, resolution, storage, and query generation.

## Architecture

Agentic GraphRAG has two main data flows:

```text
Ingestion: source -> document -> chunk -> mentions -> matched graph -> indexes
Query:     question -> plan -> research -> verify -> cited answer
```

## Ingestion Pipeline

`Graph.add()` is the single entry point for adding content. The pipeline has six stages:

1. Load: Select a loader by format. Decode or parse the source. Preserve source metadata. Apply `RAISE`, `SKIP`, or `QUARANTINE` as the error policy for each source.
2. Chunk: Use Docling layout-aware chunking for documents that Docling read. Use Chonkie chunkers for text and record documents. Rules pick the chunker for each document.
3. Extract: Run GLiNER locally against the active schema. Escalate weak results to a typed BAML extraction function when configured. Validation drops entities and triples that do not conform to the schema.
4. Resolve: Apply exact, fuzzy, embedding, and LLM-verified comparison tiers. Ambiguous or failed comparisons do not match.
5. Merge: Combine the mentions of exact matches into one entity. Decide each property value and join the chunk ids that mention it. Fuzzy, embedding, and LLM matches are stored as `MATCHES` edges, not merged.
6. Store: Upsert nodes and relations, then populate graph-native or dedicated vector indexes.

The extraction cascade replaces a weak local result with the LLM result instead of combining two conflicting outputs. A chunk escalates if the local model finds no entities in a chunk of eight words or more. It also escalates if the mean entity confidence is below 0.5. Exact matches use global store-backed lookup. More expensive fuzzy and LLM comparisons run on a smaller candidate set.

<p align="center">
  <img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/readme/resolution.png" alt="Entity resolution tiers. A pair of mentions with the same label passes an exact tier, a fuzzy tier, an embedding tier, and an LLM tier. An unsure pair is never matched. A match writes MATCHES edges and a derived ResolvedEntity, and the original entities stay." width="900">
</p>

The pipeline compares only mentions with the same label, so a city and a company with the same name stay apart. A wrong match mixes the facts of two things, and a missed match can be fixed later. For that reason every tier prefers "no match" when it is not sure.

`Graph.consolidate()` provides a separate whole-graph reconciliation pass for duplicates found across ingestion runs. It runs as a dry run by default, so applications can inspect proposed matches before they apply them.

`Graph.update()` replaces a document that changed, and an unchanged document is a no-op. `Graph.delete_document()` removes a document from search and prunes entities that lose their last evidence. Both work on a document key, and each runs as one job, so a crash leaves the document whole.

## Embeddings and Storage

The async `Embedder`, `GraphStore`, and `VectorStore` interfaces keep model and database choices outside graph-construction logic.

### Embeddings

- Dense embeddings through Sentence Transformers.
- Sparse BM25 embeddings through FastEmbed.
- Batch-first async APIs with optional content-addressed caching by text and model.
- Dimension checks before collections or indexes accept vectors. `Graph.open` raises an error when the embedder does not match the stored vector dimensions.

### Graph storage

The Neo4j backend supports local Neo4j and Aura over Bolt, managed read/write transactions, node and relation upserts, constraints, indexes, and native dense vector search. The query builders validate dynamic labels and relation types before they interpolate them into Cypher.

### Vector storage

| Backend | Dense search | Hybrid search | Deployment |
| --- | --- | --- | --- |
| Neo4j | Native vector index | No | Local or Aura |
| Qdrant | Yes | Dense + sparse fusion | Local or Cloud |
| Weaviate | Yes | Native BM25/vector weighting | Custom or Cloud |
| Milvus / Zilliz | Yes | Dense + BM25 fusion | Local or Cloud |

All dedicated vector stores share collection lifecycle, batch upsert, retrieval, scrolling, counting, deletion, filtering, dense search, and hybrid search. Filters use exact scalar matches, OR within a list value, and AND across keys.

## Retrieval Pipeline

Retrieval composes small search methods into retrievers, runs them concurrently, and fuses their results through data-only recipes.

- Entity retrieval finds entities and resolved entities by dense or hybrid search and can expand matched seeds with bounded graph traversal.
- Chunk retrieval returns source passages with document and span provenance.
- Community retrieval searches community reports for thematic and corpus-wide questions.
- Text-to-Cypher retrieval generates a schema-aware, read-only query with bounded retries.
- Graph traversal uses bounded breadth-first search to collect connected evidence.

| Recipe | Search methods | Extra steps |
| --- | --- | --- |
| `ENTITY` | Entity | none |
| `CHUNK` | Chunk | none |
| `HYBRID` | Entity + chunk | none |
| `HYBRID_RERANKED` | Entity + chunk | Community reports, cross-encoder rerank |
| `GRAPH_EXPAND` | Entity | Graph walk, community reports |
| `THEMATIC` | Community | none |
| `TEXT2CYPHER` | Text-to-Cypher | none |

Reciprocal Rank Fusion merges the ranked lists, so no method's score scale takes over. A cross-encoder or graph-distance reranker can then set a new order. A recipe can ignore a failed or empty search branch and still return evidence from the remaining methods.

```python
from agrag.retrieval import HYBRID, SearchEngine

engine = SearchEngine(graph_store=graph_store, embedder=embedder, graph_schema=schema)
results = await engine.search("What treats headaches?", HYBRID)
```

## Agentic RAG Loop

<p align="center">
  <img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/readme/agent-loop.png" alt="Agent loop. A planner splits the question into sub-questions. A researcher searches the graph. A verifier returns PASS, INSUFFICIENT, or CONTRADICTORY. INSUFFICIENT sends the gaps back to the researcher. The answer carries citation keys." width="900">
</p>

The agent coordinates three roles around the retrieval layer:

- Planner: splits a question into two to four focused sub-questions and writes the final answer.
- Researcher: searches the graph with entity, chunk, community, graph, and Cypher tools. Every evidence item keeps its citation key.
- Verifier: has no tools. It checks each sub-question against the cited evidence and returns one verdict.

| Verdict | Meaning | Next step |
| --- | --- | --- |
| `PASS` | Every sub-question has supporting evidence. Nothing conflicts. | The planner writes the answer. |
| `INSUFFICIENT` | A sub-question lacks evidence, or a claim does not match its evidence. | The planner sends the gaps back to the researcher, up to three times. |
| `CONTRADICTORY` | Two cited pieces of evidence conflict. | The planner states the conflict in the answer. |

When the retry limit is reached, the planner answers from the evidence it has and names the sub-questions it did not answer. Each run keeps a ledger. The ledger maps every citation key to stored evidence. `E` means an entity, `R` means a relation, `C` means a chunk, `G` means a community report, and `V` means a query value. You can limit every search to one document or tenant.

## Structured LLM Output

BAML defines typed contracts for entity and relation extraction, entity-match verification, community reports, description summaries, and Cypher generation. Runtime client registries support a single provider, fallback chains, or round-robin routing. They route across OpenAI, Anthropic, AWS Bedrock, Google AI, Vertex AI, Azure OpenAI, and OpenAI-compatible endpoints. The agent uses an OpenAI-compatible endpoint that you set with `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID`.

## Observability and Failure Handling

OpenTelemetry API support is part of the core package. Exporters and the SDK are optional. You pass the tracer, and Agentic GraphRAG never installs a global one. Applications can send traces to any OTLP-compatible backend. Spans cover loading, chunking, extraction, model calls, resolution, storage writes, searches, and agent turns.

Long-running graph builds report bounded, structured stage statistics for ingestion, extraction, resolution, merging, and storage. Failures include the affected item, error type, message, and trace/span IDs. Full detail remains in the trace backend so result objects stay bounded on large corpora.

`agrag.eval` (the `eval` extra) holds metrics that score answers, retrieval, extraction, resolution, and agent runs on your own documents and questions. See [Score Agentic GraphRAG on your questions](https://ontogr.github.io/agentic-graphrag/guides/score-agrag-on-your-questions).

## Installation

Agentic GraphRAG requires Python 3.11 or newer.

```bash
uv pip install agentic-graphrag
```

Install only the integrations you use:

```bash
# Rich documents and local extraction
uv pip install "agentic-graphrag[docling,extract]"

# LLM extraction and local dense embeddings
uv pip install "agentic-graphrag[llm,embed-local]"

# Neo4j with a dedicated Qdrant vector store and OTLP tracing
uv pip install "agentic-graphrag[neo4j,qdrant,observability]"

# The question-answering agent
uv pip install "agentic-graphrag[agents]"

# Hierarchical community detection
uv pip install "agentic-graphrag[community]"
```

| Extra | Adds |
| --- | --- |
| `docling` | PDF, DOCX, PPTX, image, XML, and layout-aware parsing |
| `extract` | Local GLiNER 2.5 extraction |
| `llm` | BAML-powered extraction and match verification |
| `agents` | The LangGraph runtime for the question-answering agent |
| `embed-local` | Sentence Transformers dense embeddings |
| `neo4j` | Neo4j graph storage and native vector search |
| `qdrant` | Qdrant dense and hybrid search |
| `weaviate` | Weaviate dense and hybrid search |
| `milvus` | Milvus/Zilliz dense and hybrid search |
| `observability` | OpenTelemetry SDK and OTLP export |
| `community` | Leiden community detection |
| `eval` | The DeepEval and AgentEvals metrics in `agrag.eval` |
| `chunk-semantic`, `chunk-neural`, `chunk-code` | The semantic, neural, and code chunkers |

## Quickstart

You need a Neo4j database, version 5.23 or newer. The free [Neo4j Aura](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) tier works, and the full [Quickstart](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) shows the setup. Install the extras for this page with uv 0.6.9 or newer. Save your credentials as `.env` in the working directory. The file sets `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.

```bash
uv pip install "agentic-graphrag[neo4j,extract,embed-local,agents]" --torch-backend=auto
```

### Build a graph

Save this script as `build_graph.py`. It needs no LLM key.

```python
import asyncio

from agrag.common.data_models import EntityType, GraphSchema, RelationType
from agrag.embedding import build_embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import GlinerExtractor, Graph

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

The script prints the counts below. The first run downloads two models, about 385 MB in total.

```text
documents: 1
chunks: 1
entities extracted: 6
relations extracted: 3
```

### Ask a question

This step needs an OpenAI-compatible LLM endpoint. Add `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` to `.env`. Then save this script as `ask.py`:

```python
import asyncio

from agrag.agents import AgentLLMSettings, build_agent
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
BAML_LOG=off uv run python ask.py
```

The answer varies with your model. This is an example:

```text
Satya Nadella works at Microsoft (E1, E3), which was founded by Bill Gates (E2, E3, C1).
evidence keys: E1, E2, E3, E4, C1, V1
```

The agent needed two facts from two sentences. It joined them through the `Microsoft` node. Each key points to stored evidence.

### Add more content

`Graph.add()` accepts exactly one of:

- `source=`: a file, directory, glob, or list of paths.
- `text=`: raw text as one document.
- `documents=`: prebuilt `Document` objects.

```python
files = await graph.add(source="./corpus/**/*.md", return_chunks=True)
print(files.ingestion.documents, len(files.chunks))
```

### Handle source failures

```python
from agrag.loaders import ErrorPolicy

result = await graph.add(
    source="./corpus",
    error_policy=ErrorPolicy.QUARANTINE,
)

for item in result.ingestion.quarantined_items:
    print(item.item_id, item.error_message)
```

`RAISE` stops the run, `SKIP` drops the source and counts it, and `QUARANTINE` sets it aside with the reason.

### Update and delete documents

```python
await graph.update("notes/q3.md", text=new_text)
await graph.delete_document("notes/q3.md")
```

See the [documentation](https://ontogr.github.io/agentic-graphrag/) for guides and the generated API reference.

## Supported Formats

| Format | Extension(s) | Loader |
| --- | --- | --- |
| Plain text and logs | `.txt`, `.log` | Core |
| Markdown | `.md`, `.markdown` | Core |
| AsciiDoc | `.adoc`, `.asciidoc` | Docling, with core fallback |
| HTML | `.html`, `.htm` | Core |
| CSV / TSV | `.csv`, `.tsv` | Core, one document per row or one for the table |
| JSON | `.json` | Core, record-aware |
| JSON Lines | `.jsonl`, `.ndjson` | Core, one document per row |
| PDF | `.pdf` | Docling |
| Word | `.docx` | Docling |
| PowerPoint | `.pptx` | Docling |
| Images | `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp` | Docling |
| XML | `.xml` | Docling |
| Chat exports | `.json`, `.jsonl`, `.ndjson` | Chat loader, which you pass for a single file |

Core loaders remain the default for Markdown, HTML, CSV, TSV, and JSON records. Docling takes precedence for layout-rich documents and AsciiDoc when installed.

## Project Structure

```text
agrag/
├── common/data_models/   # documents, chunks, schemas, extraction and storage records
├── chunking/             # Chonkie and Docling chunk adapters
├── loaders/              # core corpus readers and optional Docling loader
├── ingestion/            # Graph API, extraction, resolution, community detection and pipeline stages
├── embedding/            # dense and sparse embedding interfaces
├── graphdb/              # graph-store interface and Neo4j backend
├── vectordb/             # vector-store interface and Qdrant/Weaviate/Milvus backends
├── cypher/               # validated Cypher builders
├── retrieval/            # search methods, retrievers, recipes and rerankers
├── agents/               # planner, researcher, verifier and citation ledger
├── eval/                 # metrics for answers, retrieval, extraction, resolution and agent runs
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

Integration tests run against local Neo4j, Qdrant, Weaviate, and Milvus services:

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
