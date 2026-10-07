---
title: agrag.ingestion
sidebar_position: 8
---


# `agrag.ingestion` \{#agrag-ingestion}

The ingestion package.

**Modules:**

- [**community**](community/index.md) – Community detection: hierarchical Leiden over the entity graph.
- [**extract**](extract/index.md) – The Extractor interface: reads one Chunk and produces an ExtractionResult.
- [**graph**](graph/index.md) – The public Graph API for ingestion.
- [**merge**](merge/index.md) – Merge mechanics: computing how a resolved group of mentions and entities combine.
- [**reports**](reports/index.md) – Reports returned by Graph pipeline operations.
- [**resolve**](resolve/index.md) – Entity resolution public API.
- [**resolved_embeddings**](resolved_embeddings/index.md) – Embedding and vector synchronization for resolved-entities.
- [**resolved_entities**](resolved_entities/index.md) – Non-destructive match persistence and resolved-entity computation.
- [**settings**](settings/index.md) – Configuration for the Cutover Job crash-recovery machine.
- [**stats**](stats/index.md) – Per-stage observability types for the ingestion pipeline.

**Classes:**

- [**AddResult**](AddResult.md) – Graph.add()'s return type — one summary per pipeline stage.
- [**BAMLExtractor**](BAMLExtractor.md) – Extracts entities and relations with an LLM through a typed BAML function.
- [**CommunityDetectionReport**](CommunityDetectionReport.md) – Report from Graph.detect_communities().
- [**ConsolidationReport**](ConsolidationReport.md) – Report from Graph.consolidate().
- [**EscalatingExtractor**](EscalatingExtractor.md) – Runs a cheap extractor on every chunk and a stronger one on weak results.
- [**ExtractionLLMSettings**](ExtractionLLMSettings.md) – Env-backed LLM client config for the extraction role.
- [**Extractor**](Extractor.md) – Reads one chunk and returns the entities and relations it contains.
- [**ExtractorMissingExtraError**](ExtractorMissingExtraError.md) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](GlinerExtractor.md) – Extracts entities and relations with a local GLiNER2.5 model.
- [**Graph**](Graph-ref.md) – A knowledge graph that a caller can open and add content to.
- [**ReevaluationReport**](ReevaluationReport.md) – Report from Graph.reevaluate().
- [**UpdateResult**](UpdateResult.md) – Summary of an update or soft deletion.
