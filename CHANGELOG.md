# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add the LegalBench-RAG benchmark ([#62](https://github.com/ontogr/agentic-graphrag/pull/62))
- Add the FinanceBench benchmark ([#67](https://github.com/ontogr/agentic-graphrag/pull/67))
- Add the GraphRAG-Bench benchmark ([#66](https://github.com/ontogr/agentic-graphrag/pull/66))
- Add the BEAM memory benchmark ([#64](https://github.com/ontogr/agentic-graphrag/pull/64))
- Shrink the Legal lite set to a quick check ([#69](https://github.com/ontogr/agentic-graphrag/pull/69))
- Add the HealthBench benchmark ([#65](https://github.com/ontogr/agentic-graphrag/pull/65))

### Changed

- Remove unused merge chain lookups ([#70](https://github.com/ontogr/agentic-graphrag/pull/70))
- Add one module for loading entities by id ([#72](https://github.com/ontogr/agentic-graphrag/pull/72))
- Move pending state behind the stores ([#73](https://github.com/ontogr/agentic-graphrag/pull/73))
- Resolve mentions in one module ([#74](https://github.com/ontogr/agentic-graphrag/pull/74))
- Split Graph by lifecycle stage ([#75](https://github.com/ontogr/agentic-graphrag/pull/75))
- Use one failure rule for retrieval ([#76](https://github.com/ontogr/agentic-graphrag/pull/76))

### Fixed

- Replay job cleanup when resuming ([#71](https://github.com/ontogr/agentic-graphrag/pull/71))
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

[unreleased]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.4..HEAD
[0.0.4]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.3..v0.0.4
[0.0.3]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.2..v0.0.3
[0.0.2]: https://github.com/ontogr/agentic-graphrag/compare/v0.0.1..v0.0.2
[0.0.1]: https://github.com/ontogr/agentic-graphrag/tree/v0.0.1
