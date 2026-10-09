---
title: agrag.common.data_models
sidebar_label: data_models
---

# `agrag.common.data_models` \{#agrag-common-data_models}

Shared data models used by agrag components.

**Modules:**

- [**chunk**](chunk/index.md) – The Chunk model: one retrieval-sized piece of a Document.
- [**community**](community/index.md) – The Community model: a Leiden-detected entity cluster with an LLM report.
- [**cutover_job**](cutover_job/index.md) – Crash-recoverable state for one add/update/delete_document call.
- [**data_point**](data_point/index.md) – The base class for a graph node.
- [**document**](document/index.md) – The Document model: one unit of source text, before chunking.
- [**entity**](entity/index.md) – A permanent mention-level graph node, accumulated by exact-name matching.
- [**extraction**](extraction/index.md) – Pre-resolution entity and relation mentions produced by an Extractor.
- [**graph_record**](graph_record/index.md) – Graph storage record shapes for GraphStore.
- [**graph_schema**](graph_schema/index.md) – The GraphSchema contract: entity and relation types extraction validates against.
- [**normalization**](normalization/index.md) – The Normalization model: how a loader turned source bytes into text.
- [**provenance**](provenance/index.md) – Provenance types for a chunk.
- [**query_value**](query_value/index.md) – A result row returned by a direct graph query.
- [**relation**](relation/index.md) – The canonical, deduped graph relationship that merge mechanics produces.
- [**resolved_entity**](resolved_entity/index.md) – Materialized identity clusters for non-destructive entity resolution.
- [**search_result**](search_result/index.md) – One retrieved item, tagged with source and relevance score.
- [**stage_failure**](stage_failure/index.md) – Per-stage failure record and its per-call cap.
- [**vector_record**](vector_record/index.md) – Vector storage record shapes shared by VectorStore and GraphStore.

**Classes:**

- [**Chunk**](chunk/Chunk-ref.md) – One retrieval-sized piece of a Document.
- [**Community**](community/Community-ref.md) – A cluster of entities detected by hierarchical Leiden, with an LLM report.
- [**Distance**](vector_record/Distance.md) – A distance metric a vector index compares embeddings with.
- [**Document**](document/Document-ref.md) – One unit of source text, before chunking.
- [**DocumentFamily**](document/DocumentFamily.md) – The shape of a document's source.
- [**Entity**](entity/Entity-ref.md) – A permanent mention-level node, never destroyed once written.
- [**EntityType**](graph_schema/EntityType.md) – One kind of entity a schema recognizes.
- [**GraphSchema**](graph_schema/GraphSchema.md) – A versioned contract of entity and relation types.
- [**NodeRecord**](graph_record/NodeRecord.md) – One graph node, ready to write.
- [**Normalization**](normalization/Normalization-ref.md) – How a loader turned source bytes into `Document.text`.
- [**PageProvenance**](provenance/PageProvenance.md) – The location of a chunk across one or more pages.
- [**Relation**](relation/Relation-ref.md) – A resolved relationship between two Entity nodes.
- [**RelationRecord**](graph_record/RelationRecord.md) – One graph relationship, ready to write.
- [**RelationType**](graph_schema/RelationType.md) – One kind of relation a schema recognizes.
- [**ResolvedEntity**](resolved_entity/ResolvedEntity.md) – A materialized cluster of entities that refer to the same thing.
- [**SearchResult**](search_result/SearchResult.md) – One retrieved item, tagged with where it came from.
- [**SourceFormat**](document/SourceFormat.md) – A source format that a loader can read.
- [**TextProvenance**](provenance/TextProvenance.md) – The location of a chunk inside flattened document text.
- [**VectorRecord**](vector_record/VectorRecord.md) – One vector and its payload, ready to write to a collection or index.

**Attributes:**

- [**GENERIC**](graph_schema/GENERIC.md) –
