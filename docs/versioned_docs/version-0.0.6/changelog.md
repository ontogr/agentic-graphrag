# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.6] - 2026-10-16

### Added

- Record the content version on each chunk ([#131](https://github.com/ontogr/agentic-graphrag/pull/131))
- Update a document from an already built Document ([#133](https://github.com/ontogr/agentic-graphrag/pull/133))
- Record each document change and make add on an existing key an update ([#140](https://github.com/ontogr/agentic-graphrag/pull/140))
- Find, fetch and cite original source passages ([#138](https://github.com/ontogr/agentic-graphrag/pull/138))
- Add durable tasks with raw events and resumable steps ([#141](https://github.com/ontogr/agentic-graphrag/pull/141))
- Add a local MCP server with read tools for source evidence ([#143](https://github.com/ontogr/agentic-graphrag/pull/143))
- Navigate around a passage and find entities with their source support ([#144](https://github.com/ontogr/agentic-graphrag/pull/144))
- Add source status and graph index readiness ([#148](https://github.com/ontogr/agentic-graphrag/pull/148))
- Record evidence-linked decisions ([#147](https://github.com/ontogr/agentic-graphrag/pull/147))
- Add task and decision MCP tools ([#149](https://github.com/ontogr/agentic-graphrag/pull/149))
- Add task and event retention operations ([#151](https://github.com/ontogr/agentic-graphrag/pull/151))
- Review decisions after source changes and reaffirm them ([#152](https://github.com/ontogr/agentic-graphrag/pull/152))
- Record agent events and resume tasks ([#154](https://github.com/ontogr/agentic-graphrag/pull/154))
- Purge a document and its evidence after cutover ([#155](https://github.com/ontogr/agentic-graphrag/pull/155))
- Add provenance-aware connected memory and agent/MCP workflows ([#157](https://github.com/ontogr/agentic-graphrag/pull/157))
- Add readable source citations ([#159](https://github.com/ontogr/agentic-graphrag/pull/159))

### Changed

- Remove generated Cypher retrieval ([#136](https://github.com/ontogr/agentic-graphrag/pull/136))
- Remove the separate Qdrant, Weaviate and Milvus backends and their extras. Vector search uses Neo4j's native indexes ([#139](https://github.com/ontogr/agentic-graphrag/pull/139)).
- Replace the agent workflow with a task-scoped agent that uses explicit document scope, project, agent and task identities ([#150](https://github.com/ontogr/agentic-graphrag/pull/150)).

### Fixed

- Make a document version's identity follow its text and structure ([#137](https://github.com/ontogr/agentic-graphrag/pull/137))
- Validate chunk content hashes ([#145](https://github.com/ontogr/agentic-graphrag/pull/145))
- Provision search indexes before running agent evaluations ([#156](https://github.com/ontogr/agentic-graphrag/pull/156))
- Read structured answers in answer and trajectory evaluations ([#158](https://github.com/ontogr/agentic-graphrag/pull/158))
- Resolve numbered citations in answer quality evaluation ([#160](https://github.com/ontogr/agentic-graphrag/pull/160))

## [0.0.5] - 2026-10-13

### Added

- Add the LegalBench-RAG benchmark ([#62](https://github.com/ontogr/agentic-graphrag/pull/62))
- Add the FinanceBench benchmark ([#67](https://github.com/ontogr/agentic-graphrag/pull/67))
- Add the GraphRAG-Bench benchmark ([#66](https://github.com/ontogr/agentic-graphrag/pull/66))
- Add the BEAM memory benchmark ([#64](https://github.com/ontogr/agentic-graphrag/pull/64))
- Shrink the Legal lite set to a quick check ([#69](https://github.com/ontogr/agentic-graphrag/pull/69))
- Add the HealthBench benchmark ([#65](https://github.com/ontogr/agentic-graphrag/pull/65))
- Use FastEmbed as the default dense embedder ([#80](https://github.com/ontogr/agentic-graphrag/pull/80))
- Store document hierarchy in the graph ([#81](https://github.com/ontogr/agentic-graphrag/pull/81))
- Add typed schema properties ([#88](https://github.com/ontogr/agentic-graphrag/pull/88))
- Add validated extraction settings and confidence levels ([#90](https://github.com/ontogr/agentic-graphrag/pull/90))
- Add schema hierarchy and relation rules ([#92](https://github.com/ontogr/agentic-graphrag/pull/92))
- Add a schema loader for dicts, label lists, JSON and YAML ([#95](https://github.com/ontogr/agentic-graphrag/pull/95))
- Add default schema and presets ([#97](https://github.com/ontogr/agentic-graphrag/pull/97))
- Export a schema as JSON Schema ([#98](https://github.com/ontogr/agentic-graphrag/pull/98))
- Export a schema as SHACL ([#100](https://github.com/ontogr/agentic-graphrag/pull/100))
- Import a schema from Pydantic classes ([#101](https://github.com/ontogr/agentic-graphrag/pull/101))
- Add JSON-LD schema export ([#102](https://github.com/ontogr/agentic-graphrag/pull/102))
- Import OWL schemas ([#103](https://github.com/ontogr/agentic-graphrag/pull/103))
- Add the candidate store and keep it out of every read path ([#104](https://github.com/ontogr/agentic-graphrag/pull/104))
- Load shipped schemas by name and accept any schema in Graph ([#105](https://github.com/ontogr/agentic-graphrag/pull/105))
- Store ancestor labels on entity nodes ([#107](https://github.com/ontogr/agentic-graphrag/pull/107))
- Read GLiNER output with confidence, parent labels and candidates ([#109](https://github.com/ontogr/agentic-graphrag/pull/109))
- Re-extract documents when the schema or settings change ([#114](https://github.com/ontogr/agentic-graphrag/pull/114))
- Escalate weak chunks to the LLM within a budget ([#116](https://github.com/ontogr/agentic-graphrag/pull/116))
- Ask the LLM for names and labels only and find spans in code ([#119](https://github.com/ontogr/agentic-graphrag/pull/119))
- Add document dates and refresh controls ([#121](https://github.com/ontogr/agentic-graphrag/pull/121))
- Capture extraction candidates ([#123](https://github.com/ontogr/agentic-graphrag/pull/123))
- Review and convert candidates ([#124](https://github.com/ontogr/agentic-graphrag/pull/124))

### Changed

- Remove unused merge chain lookups ([#70](https://github.com/ontogr/agentic-graphrag/pull/70))
- Add one module for loading entities by id ([#72](https://github.com/ontogr/agentic-graphrag/pull/72))
- Move pending state behind the stores ([#73](https://github.com/ontogr/agentic-graphrag/pull/73))
- Resolve mentions in one module ([#74](https://github.com/ontogr/agentic-graphrag/pull/74))
- Split Graph by lifecycle stage ([#75](https://github.com/ontogr/agentic-graphrag/pull/75))
- Use one failure rule for retrieval ([#76](https://github.com/ontogr/agentic-graphrag/pull/76))
- Shorten node identity and merge alias labels ([#86](https://github.com/ontogr/agentic-graphrag/pull/86))
- Rename structural edges to HAS_PART ([#87](https://github.com/ontogr/agentic-graphrag/pull/87))
- Index the pending tag for commit and rollback ([#110](https://github.com/ontogr/agentic-graphrag/pull/110))

### Fixed

- Replay job cleanup when resuming ([#71](https://github.com/ontogr/agentic-graphrag/pull/71))
- Protect credentials and settings loading ([#89](https://github.com/ontogr/agentic-graphrag/pull/89))
- Preserve undecided entity matches ([#91](https://github.com/ontogr/agentic-graphrag/pull/91))
- Retry graph transactions ([#93](https://github.com/ontogr/agentic-graphrag/pull/93))
- Reject schema names that collide with names the graph writes itself ([#96](https://github.com/ontogr/agentic-graphrag/pull/96))
- Protect committed jobs from rollback ([#99](https://github.com/ontogr/agentic-graphrag/pull/99))
- Guard match deactivation against pending edges ([#106](https://github.com/ontogr/agentic-graphrag/pull/106))
- Close gaps in the generated-Cypher gate ([#108](https://github.com/ontogr/agentic-graphrag/pull/108))
- Roll back an expired pending job before another job takes its document ([#111](https://github.com/ontogr/agentic-graphrag/pull/111))
- Validate the output of every extractor against the schema ([#112](https://github.com/ontogr/agentic-graphrag/pull/112))
- Defer job writes over committed rows to commit ([#113](https://github.com/ontogr/agentic-graphrag/pull/113))
- Keep concurrent jobs from losing a shared relation ([#115](https://github.com/ontogr/agentic-graphrag/pull/115))
- Resolve entities that concurrent adds create ([#117](https://github.com/ontogr/agentic-graphrag/pull/117))
- Write each document batch before extracting the next ([#118](https://github.com/ontogr/agentic-graphrag/pull/118))
- Cover the splitter in the chunker fingerprint ([#120](https://github.com/ontogr/agentic-graphrag/pull/120))
- Bound LLM requests and improve retries ([#122](https://github.com/ontogr/agentic-graphrag/pull/122))
- Cap selectolax below 1.0

## [0.0.4] - 2026-09-30

### Fixed

- Silence Neo4j warnings, stabilize imports and safety guards ([#59](https://github.com/ontogr/agentic-graphrag/pull/59))

## [0.0.3] - 2026-09-30

### Added

- Upgrade CI Milvus stack to v3.0 and pull MinIO from quay.io ([#12](https://github.com/ontogr/agentic-graphrag/pull/12))
- Add hierarchical community detection ([#13](https://github.com/ontogr/agentic-graphrag/pull/13))
- Isolate per-item failures in GraphStore bulk writes ([#18](https://github.com/ontogr/agentic-graphrag/pull/18))
- Track document identity and versioning in the graph ([#19](https://github.com/ontogr/agentic-graphrag/pull/19))
- Add candidate search and non-destructive entity resolution ([#25](https://github.com/ontogr/agentic-graphrag/pull/25))
- Add schema-aware research loop with flexible graph tools ([#26](https://github.com/ontogr/agentic-graphrag/pull/26))
- Resolve entity description conflicts via LLM ([#27](https://github.com/ontogr/agentic-graphrag/pull/27))
- Send neighbors and similarity to batched LLM verification ([#28](https://github.com/ontogr/agentic-graphrag/pull/28))
- Crash-safe graph mutation with non-destructive resolution ([#29](https://github.com/ontogr/agentic-graphrag/pull/29))
- Return the run ledger from agent `ainvoke` ([#33](https://github.com/ontogr/agentic-graphrag/pull/33))
- Add eval judge, median metric and CI evals ([#34](https://github.com/ontogr/agentic-graphrag/pull/34))
- Trace agent runs using OpenInference callback ([#35](https://github.com/ontogr/agentic-graphrag/pull/35))
- Add extraction quality evaluation ([#37](https://github.com/ontogr/agentic-graphrag/pull/37))
- Add answer quality evaluation ([#38](https://github.com/ontogr/agentic-graphrag/pull/38))
- Add entity resolution quality evaluation ([#39](https://github.com/ontogr/agentic-graphrag/pull/39))
- Add verifier calibration eval ([#40](https://github.com/ontogr/agentic-graphrag/pull/40))
- Per-sentence citation report and noise-tolerant answer gate ([#42](https://github.com/ontogr/agentic-graphrag/pull/42))
- Add agent trajectory evaluation ([#43](https://github.com/ontogr/agentic-graphrag/pull/43))
- Add per-document loader spans, retire traced decorator ([#44](https://github.com/ontogr/agentic-graphrag/pull/44))
- Trace the ingestion pipeline with OpenTelemetry spans ([#46](https://github.com/ontogr/agentic-graphrag/pull/46))
- Trace graph store, vector store and embedder with OpenTelemetry ([#47](https://github.com/ontogr/agentic-graphrag/pull/47))
- Trace every LLM call with per-request spans ([#48](https://github.com/ontogr/agentic-graphrag/pull/48))
- Add OpenTelemetry tracing to retrieval and agent tools ([#50](https://github.com/ontogr/agentic-graphrag/pull/50))
- Rework chunking with an explicit Chunker contract, rules and new strategies ([#51](https://github.com/ontogr/agentic-graphrag/pull/51))
- Add benchmark harness ([#57](https://github.com/ontogr/agentic-graphrag/pull/57))

### Changed

- Move StageFailure to common/data_models, fix loaders/ingestion cycle ([#45](https://github.com/ontogr/agentic-graphrag/pull/45))
- Move rule files into project skills ([#49](https://github.com/ontogr/agentic-graphrag/pull/49))

### Fixed

- Synthesize `SimpleAgent` answers with the LLM ([#30](https://github.com/ontogr/agentic-graphrag/pull/30))

## [0.0.2] - 2026-09-01

### Added

- Add .claude and expand AGENTS.md with agent rules ([#1](https://github.com/ontogr/agentic-graphrag/pull/1))
- Add ingestion layer with Graph.add and docling loaders ([#3](https://github.com/ontogr/agentic-graphrag/pull/3))
- Add entity extraction, resolution, and LLM clients ([#4](https://github.com/ontogr/agentic-graphrag/pull/4))
- Harden extraction and resolution against LLM edge cases ([#6](https://github.com/ontogr/agentic-graphrag/pull/6))
- Add embedder, vector store, and graph store backends ([#5](https://github.com/ontogr/agentic-graphrag/pull/5))
- Wire Graph.add pipeline with field-level merge and Graph.consolidate ([#7](https://github.com/ontogr/agentic-graphrag/pull/7))
- Add retrieval layer and agentic answering ([#8](https://github.com/ontogr/agentic-graphrag/pull/8))

## [0.0.1] - 2026-08-25

[unreleased]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.6..HEAD
[0.0.6]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.5..v0.0.6
[0.0.5]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.4..v0.0.5
[0.0.4]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.3..v0.0.4
[0.0.3]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.2..v0.0.3
[0.0.2]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.1..v0.0.2
[0.0.1]: https://github.com/ontogr/agentic-graphrag/tree/v0.0.1
