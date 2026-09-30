<h1 align="center">Agentic GraphRAG</h1>

<p align="center"><strong>Turn your documents into a knowledge graph. Ask questions that an agent answers with citations.</strong></p>

<p align="center">
[![PyPI](https://img.shields.io/pypi/v/agentic-graphrag.svg)](https://pypi.org/project/agentic-graphrag/) [![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/agentic-graphrag/) [![CI](https://img.shields.io/github/actions/workflow/status/ontogr/agentic-graphrag/ci.yml?branch=main&label=CI&logo=githubactions)](https://github.com/ontogr/agentic-graphrag/actions/workflows/ci.yml) [![Codecov](https://codecov.io/gh/ontogr/agentic-graphrag/branch/main/graph/badge.svg)](https://codecov.io/gh/ontogr/agentic-graphrag) [![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=readthedocs)](https://ontogr.github.io/agentic-graphrag/) [![License](https://img.shields.io/github/license/ontogr/agentic-graphrag?color=green)](LICENSE)
</p>

<p align="center"><img src="https://raw.githubusercontent.com/ontogr/agentic-graphrag/main/docs/static/img/hero-banner.png" alt="Agentic GraphRAG pipeline: sources, load and chunk, extract, resolve, graph and vector stores, retrieve, plan, research, verify, cited answer" width="900"></p>

## What it does

- **Loads your files.** One `Graph.add()` call reads text, Markdown, HTML, CSV, JSON, and, with Docling, PDF, Word, PowerPoint, and images.
- **Extracts with a schema you define.** You name the entity types, the relation types, and the valid patterns. A local GLiNER model runs first. An LLM can take over for weak chunks.
- **Merges duplicates with care.** Exact, fuzzy, embedding, and LLM-checked tiers compare mentions. An uncertain or failed comparison never merges. Matches are stored as edges, so both entities stay in the graph.
- **Retrieves across graph and vectors.** Entity, chunk, community, text-to-Cypher, and graph-expansion search run together. Reciprocal rank fusion and reranking order the results.
- **Answers with citations.** An agent plans sub-questions, researches them, and verifies the evidence. Each claim points to a source. OpenTelemetry records the run.

## Quickstart

You need Python 3.11 or newer, a free [Neo4j Aura](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) instance, and about 10 minutes. The [full Quickstart](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) shows each step, including the Aura setup.

```bash
uv venv && source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu   # skip on a GPU machine
uv pip install "agentic-graphrag[neo4j,extract,embed-local]"
```

Save the credentials file from Aura as `.env` in your working directory. It sets `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`. Then save this script as `build_graph.py`:

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


asyncio.run(main())
```

Run `python build_graph.py`. The first run downloads two models, about 385 MB. The script prints `documents: 1`, `chunks: 1`, `entities extracted: 6`, and `relations extracted: 3`. The [Quickstart](https://ontogr.github.io/agentic-graphrag/get-started/quickstart) then shows how to look at the graph and ask it a question.

## How it compares

| | agrag | Microsoft GraphRAG | LightRAG | Neo4j GraphRAG (Python) | FalkorDB GraphRAG-SDK |
| --- | --- | --- | --- | --- | --- |
| **License · Python** | [Apache-2.0 · 3.11+](pyproject.toml) | [MIT · 3.11–3.13](https://pypi.org/project/graphrag/) | [MIT · 3.10+](https://pypi.org/project/lightrag-hku/) | [Apache-2.0 · 3.10–3.14](https://pypi.org/project/neo4j-graphrag/) | [Apache-2.0 · 3.10+](https://pypi.org/project/graphrag-sdk/) |
| **Graph store** | [Neo4j](https://ontogr.github.io/agentic-graphrag/concepts/graph-storage) | [Output tables in file, memory, blob, or Cosmos DB storage](https://microsoft.github.io/graphrag/config/yaml/) | [Neo4j, Memgraph, NetworkX](https://github.com/HKUDS/LightRAG) | [Neo4j](https://neo4j.com/docs/neo4j-graphrag-python/current/) | [FalkorDB](https://github.com/FalkorDB/GraphRAG-SDK) |
| **Vector store** | [Neo4j index, Qdrant, Weaviate, Milvus](https://ontogr.github.io/agentic-graphrag/concepts/graph-storage) | [LanceDB, Azure AI Search, Cosmos DB](https://microsoft.github.io/graphrag/config/yaml/) | [Several, including Milvus and Qdrant](https://github.com/HKUDS/LightRAG) | [Neo4j index; Weaviate, Pinecone, and Qdrant retrievers](https://neo4j.com/docs/neo4j-graphrag-python/current/) | [Not stated](https://docs.falkordb.com/genai-tools/graphrag-sdk) |
| **Schema** | [You define types and patterns](https://ontogr.github.io/agentic-graphrag/concepts/extraction) | [You list `entity_types`](https://microsoft.github.io/graphrag/config/yaml/) | [Not stated](https://github.com/HKUDS/LightRAG) | [You define types and patterns, or an LLM extracts them](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html) | [Optional, user defined](https://github.com/FalkorDB/GraphRAG-SDK) |
| **Entity resolution** | [Exact, fuzzy, embedding, and LLM-checked tiers](https://ontogr.github.io/agentic-graphrag/concepts/resolution) | [Same title and type merge](https://microsoft.github.io/graphrag/index/default_dataflow/) | [Merge steps, method not described](https://github.com/HKUDS/LightRAG) | [Exact, spaCy, and fuzzy resolvers](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html) | [A deduplication step](https://github.com/FalkorDB/GraphRAG-SDK) |
| **Community reports** | [Leiden communities with reports](https://ontogr.github.io/agentic-graphrag/concepts/communities) | [Hierarchical Leiden with summaries](https://microsoft.github.io/graphrag/index/default_dataflow/) | [Not used, per the README](https://github.com/HKUDS/LightRAG) | [Not stated](https://neo4j.com/docs/neo4j-graphrag-python/current/) | [Not stated](https://github.com/FalkorDB/GraphRAG-SDK) |
| **Query modes** | [Entity, chunk, community, text-to-Cypher, graph expansion](https://ontogr.github.io/agentic-graphrag/concepts/retrieval) | [Global, Local, DRIFT, Basic](https://microsoft.github.io/graphrag/) | [local, global, hybrid, naive, mix](https://github.com/HKUDS/LightRAG) | [Vector, hybrid, text-to-Cypher, and Cypher-augmented retrievers](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html) | [Vector, full-text, Cypher, relationship expansion](https://docs.falkordb.com/genai-tools/graphrag-sdk) |
| **Agent** | [Plan, research, verify loop](https://ontogr.github.io/agentic-graphrag/concepts/agent-loop) | [Not stated](https://microsoft.github.io/graphrag/) | [Not stated](https://github.com/HKUDS/LightRAG) | [`ToolsRetriever`: an LLM picks retrieval tools](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html) | [Not stated](https://github.com/FalkorDB/GraphRAG-SDK) |
| **Tracing** | [OpenTelemetry through an injected tracer](https://ontogr.github.io/agentic-graphrag/concepts/observability) | [Not stated](https://microsoft.github.io/graphrag/) | [Langfuse integration](https://github.com/HKUDS/LightRAG) | [Not stated](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html) | [Not stated](https://github.com/FalkorDB/GraphRAG-SDK) |

Facts come from each project's own pages, linked in each cell and checked on 2026-09-30. "Not stated" means the linked page does not say. It does not mean the feature is absent.

## Learn more

- **Start:** [Introduction](https://ontogr.github.io/agentic-graphrag/get-started/introduction) · [Installation](https://ontogr.github.io/agentic-graphrag/get-started/installation) · [Quickstart](https://ontogr.github.io/agentic-graphrag/get-started/quickstart)
- **Concepts:** [Architecture](https://ontogr.github.io/agentic-graphrag/concepts/architecture) · [Knowledge graph](https://ontogr.github.io/agentic-graphrag/concepts/knowledge-graph) · [Ingestion](https://ontogr.github.io/agentic-graphrag/concepts/ingestion) · [Loading](https://ontogr.github.io/agentic-graphrag/concepts/loading) · [Chunking](https://ontogr.github.io/agentic-graphrag/concepts/chunking) · [Extraction](https://ontogr.github.io/agentic-graphrag/concepts/extraction) · [Entity resolution](https://ontogr.github.io/agentic-graphrag/concepts/resolution) · [Resolved entities](https://ontogr.github.io/agentic-graphrag/concepts/resolved-entities) · [Communities](https://ontogr.github.io/agentic-graphrag/concepts/communities) · [Agent loop](https://ontogr.github.io/agentic-graphrag/concepts/agent-loop) · [Retrieval](https://ontogr.github.io/agentic-graphrag/concepts/retrieval) · [Graph storage](https://ontogr.github.io/agentic-graphrag/concepts/graph-storage) · [Observability](https://ontogr.github.io/agentic-graphrag/concepts/observability)
- **Guides:** [Ingest documents](https://ontogr.github.io/agentic-graphrag/guides/ingest-documents) · [Update and delete documents](https://ontogr.github.io/agentic-graphrag/guides/update-and-delete-documents) · [Define a graph schema](https://ontogr.github.io/agentic-graphrag/guides/define-a-graph-schema) · [Configure chunking](https://ontogr.github.io/agentic-graphrag/guides/configure-chunking) · [Extract and resolve](https://ontogr.github.io/agentic-graphrag/guides/extract-and-resolve) · [Consolidate duplicates](https://ontogr.github.io/agentic-graphrag/guides/consolidate-duplicates) · [Detect communities](https://ontogr.github.io/agentic-graphrag/guides/detect-communities) · [Configure storage backends](https://ontogr.github.io/agentic-graphrag/guides/configure-storage-backends) · [Retrieve and answer](https://ontogr.github.io/agentic-graphrag/guides/retrieve-and-answer) · [Trace an agent run](https://ontogr.github.io/agentic-graphrag/guides/trace-an-agent-run) · [Score on your questions](https://ontogr.github.io/agentic-graphrag/guides/score-agrag-on-your-questions) · [Troubleshoot common errors](https://ontogr.github.io/agentic-graphrag/guides/troubleshoot-common-errors)
- **Reference:** [Core API](https://ontogr.github.io/agentic-graphrag/api) · [Configuration](https://ontogr.github.io/agentic-graphrag/reference/configuration) · [Trace spans](https://ontogr.github.io/agentic-graphrag/reference/trace-spans)

<details>
<summary>How it works</summary>

```text
Ingest:  source -> load -> chunk -> extract -> resolve -> store (graph and vector indexes)
Query:   question -> plan -> retrieve in parallel -> verify -> cited answer
```

`Graph.add()` runs the ingest flow. `Graph.consolidate()` compares entities across earlier runs (dry run by default). `Graph.detect_communities()` writes a report for each group of related entities. See [Architecture](https://ontogr.github.io/agentic-graphrag/concepts/architecture).

**Graph model**

```text
(:Document)-[:PART_OF]->(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONED_IN]->(entity)
(entity)-[:<RELATION_TYPE>]->(entity)
(entity)-[:MATCHES]->(entity)
(entity)-[:RESOLVED_AS]->(:ResolvedEntity)
(entity)-[:MEMBER_OF]->(:Community)
```

An entity node carries its schema type as a label, for example `:Person`. A community node holds its report. See [Knowledge graph](https://ontogr.github.io/agentic-graphrag/concepts/knowledge-graph).

</details>

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
<summary>Formats and storage</summary>

- **Core readers:** `.txt` `.log` `.md` `.markdown` `.html` `.htm` `.csv` `.tsv` `.json` `.jsonl` `.ndjson` `.adoc` `.asciidoc`
- **Docling** (`docling` extra): `.pdf` `.docx` `.pptx` `.xml` and the images `.png` `.jpg` `.jpeg` `.tif` `.tiff` `.bmp`

| Store | Dense search | Hybrid search | Runs |
| --- | --- | --- | --- |
| Neo4j | Native vector index | No | Local or Aura |
| Qdrant | Yes | Dense and BM25, blended by weight | Local or cloud |
| Weaviate | Yes | Native | Local or cloud |
| Milvus and Zilliz | Yes | Native BM25 | Local or cloud |

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and pull request rules. Report a problem in [Issues](https://github.com/ontogr/agentic-graphrag/issues). Apache License 2.0: see [LICENSE](LICENSE).
