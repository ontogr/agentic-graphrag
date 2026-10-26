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
- [**merge**](merge/index.md) – Merge mechanics: how a resolved group of mentions and entities combine.
- [**reports**](reports/index.md) – Reports returned by Graph pipeline operations.
- [**resolve**](resolve/index.md) – Entity resolution public API.
- [**resolved_embeddings**](resolved_embeddings/index.md) – Embedding writes and sync status for resolved entities.
- [**resolved_entities**](resolved_entities/index.md) – Non-destructive match persistence and resolved-entity computation.
- [**settings**](settings/index.md) – Configuration for ingestion: the Cutover Job and local extraction.
- [**stats**](stats/index.md) – Per-stage observability types for the ingestion pipeline.
- [**vector_sync**](vector_sync/index.md) – Synchronize graph-owned embeddings with an external vector store.

**Classes:**

- [**AddResult**](reports/add_result/AddResult.md) – Return type of Graph.add(). One summary per pipeline stage.
- [**BAMLExtractor**](extract/BAMLExtractor.md) – Extract entities and relations with an LLM through a typed BAML function.
- [**CommunityDetectionReport**](reports/community_detection_report/CommunityDetectionReport.md) – Report from Graph.detect_communities().
- [**ConsolidationReport**](reports/consolidation_report/ConsolidationReport.md) – Report from Graph.consolidate().
- [**EscalationReport**](reports/escalation_report/EscalationReport.md) – How many chunks the LLM extractor read, and how many it left alone.
- [**ExtractionLLMSettings**](extract/ExtractionLLMSettings.md) – Env-backed LLM client configuration for the extraction role.
- [**ExtractionSettings**](settings/ExtractionSettings.md) – Configuration for local entity and relation extraction.
- [**Extractor**](extract/Extractor.md) – Reads one chunk and returns the entities and relations it contains.
- [**ExtractorMissingExtraError**](extract/ExtractorMissingExtraError.md) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](extract/GlinerExtractor.md) – Extracts entities and relations with a local GLiNER2.5 model.
- [**Graph**](graph/Graph-ref.md) – A knowledge graph that a caller can open and add content to.
- [**LLMExtractor**](extract/LLMExtractor.md) – LLM role that may receive entities found by an earlier extractor.
- [**ReevaluationReport**](reports/reevaluation_report/ReevaluationReport.md) – Report from Graph.reevaluate().
- [**UnparsableExtractionError**](extract/UnparsableExtractionError.md) – The LLM replied, but the reply holds no JSON answer.
- [**UpdateResult**](reports/update_result/UpdateResult.md) – Summary of an update or soft deletion.
