---
title: agrag.common.data_models
sidebar_label: data_models
---

# `agrag.common.data_models` \{#agrag-common-data_models}

Shared data models used by agrag components.

**Modules:**

- [**candidate**](candidate/index.md) – Candidate items rejected by the extraction schema.
- [**candidate_review**](candidate_review/index.md) – Models for candidate review and schema patches.
- [**chunk**](chunk/index.md) – The Chunk model: one retrieval-sized piece of a Document.
- [**community**](community/index.md) – The Community model: a Leiden-detected entity cluster with an LLM report.
- [**cutover_job**](cutover_job/index.md) – Names and lifecycle states of the Cutover Job node.
- [**data_point**](data_point/index.md) – The base class for a graph node.
- [**decision**](decision/index.md) – Models for decision records: choices, their evidence supports and reads.
- [**default_schema**](default_schema/index.md) – The default schema: nine entity types and eight typed relations.
- [**document**](document/index.md) – The Document model: one unit of source text, before chunking.
- [**dropped**](dropped/index.md) – Counts of items discarded during extraction or merge.
- [**entity**](entity/index.md) – A permanent mention-level graph node, accumulated by exact-name matching.
- [**evidence**](evidence/index.md) – Models for evidence references, discovery results, fetch outcomes and citations.
- [**extraction**](extraction/index.md) – Pre-resolution entity and relation mentions produced by an Extractor.
- [**graph_record**](graph_record/index.md) – Graph storage record shapes for GraphStore.
- [**graph_schema**](graph_schema/index.md) – The GraphSchema contract: entity and relation types extraction validates against.
- [**entity_search**](entity_search/index.md) – Entity search and bounded graph exploration results.
- [**memory_result**](memory_result/index.md) – Error codes and the base result of every project memory write.
- [**navigation**](navigation/index.md) – Models for bounded navigation around one evidence passage.
- [**normalization**](normalization/index.md) – The Normalization model: how a loader turned source bytes into text.
- [**presets**](presets/index.md) – Preset schema fragments that add entity types to a base schema.
- [**provenance**](provenance/index.md) – Provenance types for a chunk.
- [**relation**](relation/index.md) – The canonical, deduped graph relationship that merge mechanics produces.
- [**resolved_entity**](resolved_entity/index.md) – Identity clusters for non-destructive entity resolution.
- [**search_result**](search_result/index.md) – One retrieved item, tagged with source and relevance score.
- [**stage_failure**](stage_failure/index.md) – Per-stage failure record and its per-call cap.
- [**structure**](structure/index.md) – Stable keys, node ids, reading order and ancestry for the sections of a Document.
- [**task**](task/index.md) – Models for durable task state: tasks, raw events, steps and resume views.
- [**update_decision**](update_decision/index.md) – Outcomes for updating a stored document.
- [**vector_record**](vector_record/index.md) – Vector index types shared by the graph store and retrieval.

**Classes:**

- [**Cardinality**](graph_schema/Cardinality.md) – Declared limits on distinct endpoints of one relation, across its patterns.
- [**Chunk**](chunk/Chunk-ref.md) – One retrieval-sized piece of a Document.
- [**Community**](community/Community-ref.md) – A cluster of entities detected by hierarchical Leiden, with an LLM report.
- [**Distance**](vector_record/Distance.md) – A distance metric a vector index compares embeddings with.
- [**Document**](document/Document-ref.md) – One unit of source text, before chunking.
- [**DocumentFamily**](document/DocumentFamily.md) – The shape of a document's source.
- [**DocumentSection**](document/DocumentSection.md) – One heading of a document and the content directly under it.
- [**Entity**](entity/Entity-ref.md) – A permanent mention-level node, never destroyed once written.
- [**EntityType**](graph_schema/EntityType.md) – One kind of entity a schema recognizes.
- [**GraphSchema**](graph_schema/GraphSchema.md) – A versioned contract of entity and relation types.
- [**NodeRecord**](graph_record/NodeRecord.md) – One graph node, ready to write.
- [**Normalization**](normalization/Normalization-ref.md) – How a loader turned source bytes into `Document.text`.
- [**PageProvenance**](provenance/PageProvenance.md) – The location of a chunk across one or more pages.
- [**Preset**](presets/Preset.md) – A curated set of entity types to add to a base schema.
- [**PropertySpec**](graph_schema/PropertySpec.md) – The declaration of one property on an entity type.
- [**Relation**](relation/Relation-ref.md) – A resolved relationship between two Entity nodes.
- [**RelationRecord**](graph_record/RelationRecord.md) – One graph relationship, ready to write.
- [**RelationType**](graph_schema/RelationType.md) – One kind of relation a schema recognizes.
- [**ResolvedEntity**](resolved_entity/ResolvedEntity.md) – A cluster of entities that refer to the same thing.
- [**SearchResult**](search_result/SearchResult.md) – One retrieved item, tagged with where it came from.
- [**SourceFormat**](document/SourceFormat.md) – A source format that a loader can read.
- [**TextProvenance**](provenance/TextProvenance.md) – The location of a chunk inside flattened document text.
- [**Unit**](document/Unit.md) – One piece of content in a section, such as a paragraph or a table.
- [**UnitKind**](document/UnitKind.md) – The kind of content in a unit.

**Attributes:**

- [**DEFAULT_SCHEMA**](default_schema/DEFAULT_SCHEMA-ref.md) –
- [**LEGAL**](presets/LEGAL.md) – Legal types: contracts and regulations.
- [**OPERATIONS**](presets/OPERATIONS.md) – Operations types: facilities, services and occupations.
