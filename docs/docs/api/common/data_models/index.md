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
- [**resolved_entity**](resolved_entity/index.md) – Identity clusters for non-destructive entity resolution.
- [**search_result**](search_result/index.md) – One retrieved item, tagged with source and relevance score.
- [**stage_failure**](stage_failure/index.md) – Per-stage failure record and its per-call cap.
- [**vector_record**](vector_record/index.md) – Vector storage record shapes shared by VectorStore and GraphStore.

**Classes:**

- [**Chunk**](Chunk-ref.md) – One retrieval-sized piece of a Document.
- [**Community**](Community-ref.md) – A cluster of entities detected by hierarchical Leiden, with an LLM report.
- [**Distance**](Distance.md) – A distance metric a vector index compares embeddings with.
- [**Document**](Document-ref.md) – One unit of source text, before chunking.
- [**DocumentFamily**](DocumentFamily.md) – The shape of a document's source.
- [**Entity**](Entity-ref.md) – A permanent mention-level node, never destroyed once written.
- [**EntityType**](EntityType.md) – One kind of entity a schema recognizes.
- [**GraphSchema**](GraphSchema.md) – A versioned contract of entity and relation types.
- [**NodeRecord**](NodeRecord.md) – One graph node, ready to write.
- [**Normalization**](Normalization-ref.md) – How a loader turned source bytes into `Document.text`.
- [**PageProvenance**](PageProvenance.md) – The location of a chunk across one or more pages.
- [**Relation**](Relation-ref.md) – A resolved relationship between two Entity nodes.
- [**RelationRecord**](RelationRecord.md) – One graph relationship, ready to write.
- [**RelationType**](RelationType.md) – One kind of relation a schema recognizes.
- [**ResolvedEntity**](ResolvedEntity.md) – A cluster of entities that refer to the same thing.
- [**SearchResult**](SearchResult.md) – One retrieved item, tagged with where it came from.
- [**SourceFormat**](SourceFormat.md) – A source format that a loader can read.
- [**TextProvenance**](TextProvenance.md) – The location of a chunk inside flattened document text.
- [**VectorRecord**](VectorRecord.md) – One vector and its payload, ready to write to a collection or index.

**Attributes:**

- [**GENERIC**](GENERIC.md) – A ready-made schema for open-domain text.
