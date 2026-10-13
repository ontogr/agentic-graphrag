---
title: agrag.common.data_models.candidate.CandidateRecord
sidebar_label: CandidateRecord
---

# `agrag.common.data_models.candidate.CandidateRecord` \{#agrag-common-data_models-candidate-CandidateRecord}

Bases: <code>BaseModel</code>

One rejected extraction item, stored outside the entity graph.

Each job uses a new node id. The key groups sightings across jobs without
changing a committed node's count. Entity and property candidates need
text. Relation endpoints need an entity id or unresolved text.

**Attributes:**

- [**id**](#agrag-common-data_models-candidate-CandidateRecord-id) (<code>UUID</code>) – Per-job node id, random unless supplied by the caller.
- [**kind**](#agrag-common-data_models-candidate-CandidateRecord-kind) (<code>[CandidateKind](CandidateKind.md)</code>) – Entity, relation or property candidate.
- [**label**](#agrag-common-data_models-candidate-CandidateRecord-label) (<code>str</code>) – Proposed entity type, relation type or property name.
- [**text**](#agrag-common-data_models-candidate-CandidateRecord-text) (<code>str</code>) – Entity surface text or property value. Empty for relations.
- [**source_text**](#agrag-common-data_models-candidate-CandidateRecord-source_text) (<code>str | None</code>) – Unresolved source endpoint or property holder text.
- [**target_text**](#agrag-common-data_models-candidate-CandidateRecord-target_text) (<code>str | None</code>) – Unresolved target endpoint text.
- [**confidence**](#agrag-common-data_models-candidate-CandidateRecord-confidence) (<code>float</code>) – Extractor score from 0 to 1. Use 0 for an unscored item.
- [**reason**](#agrag-common-data_models-candidate-CandidateRecord-reason) (<code>[CandidateReason](CandidateReason.md)</code>) – Why the extractor rejected the item.
- [**chunk_id**](#agrag-common-data_models-candidate-CandidateRecord-chunk_id) (<code>UUID</code>) – Evidence chunk id.
- [**source_entity_id**](#agrag-common-data_models-candidate-CandidateRecord-source_entity_id) (<code>UUID | None</code>) – Source endpoint or property holder, when resolved.
- [**target_entity_id**](#agrag-common-data_models-candidate-CandidateRecord-target_entity_id) (<code>UUID | None</code>) – Target endpoint, when resolved.
- [**source_label**](#agrag-common-data_models-candidate-CandidateRecord-source_label) (<code>str | None</code>) – Source endpoint or property holder type, when known.
- [**target_label**](#agrag-common-data_models-candidate-CandidateRecord-target_label) (<code>str | None</code>) – Target endpoint type, when known.
- [**state**](#agrag-common-data_models-candidate-CandidateRecord-state) (<code>[CandidateState](CandidateState.md)</code>) – Review state, initially pending.
- [**count**](#agrag-common-data_models-candidate-CandidateRecord-count) (<code>int</code>) – Sightings represented by this node, fixed on creation.
- [**schema_fingerprint**](#agrag-common-data_models-candidate-CandidateRecord-schema_fingerprint) (<code>str</code>) – Schema used to extract the item, empty if unknown.

## `chunk_id` \{#agrag-common-data_models-candidate-CandidateRecord-chunk_id}

```python
chunk_id: UUID
```

## `confidence` \{#agrag-common-data_models-candidate-CandidateRecord-confidence}

```python
confidence: float = Field(ge=0.0, le=1.0)
```

## `count` \{#agrag-common-data_models-candidate-CandidateRecord-count}

```python
count: int = Field(default=1, ge=1)
```

## `evidence_edge_id` \{#agrag-common-data_models-candidate-CandidateRecord-evidence_edge_id}

```python
evidence_edge_id: UUID
```

Return the deterministic evidence edge id.

## `id` \{#agrag-common-data_models-candidate-CandidateRecord-id}

```python
id: UUID = Field(default_factory=uuid4)
```

## `key` \{#agrag-common-data_models-candidate-CandidateRecord-key}

```python
key: str
```

Return the stable deduplication key for this record.

## `kind` \{#agrag-common-data_models-candidate-CandidateRecord-kind}

```python
kind: CandidateKind
```

## `label` \{#agrag-common-data_models-candidate-CandidateRecord-label}

```python
label: str = Field(min_length=1)
```

## `reason` \{#agrag-common-data_models-candidate-CandidateRecord-reason}

```python
reason: CandidateReason
```

## `schema_fingerprint` \{#agrag-common-data_models-candidate-CandidateRecord-schema_fingerprint}

```python
schema_fingerprint: str = ''
```

## `source_edge_id` \{#agrag-common-data_models-candidate-CandidateRecord-source_edge_id}

```python
source_edge_id: UUID | None
```

Return the deterministic source edge id when its endpoint exists.

## `source_entity_id` \{#agrag-common-data_models-candidate-CandidateRecord-source_entity_id}

```python
source_entity_id: UUID | None = None
```

## `source_label` \{#agrag-common-data_models-candidate-CandidateRecord-source_label}

```python
source_label: str | None = None
```

## `source_text` \{#agrag-common-data_models-candidate-CandidateRecord-source_text}

```python
source_text: str | None = None
```

## `state` \{#agrag-common-data_models-candidate-CandidateRecord-state}

```python
state: CandidateState = 'pending'
```

## `target_edge_id` \{#agrag-common-data_models-candidate-CandidateRecord-target_edge_id}

```python
target_edge_id: UUID | None
```

Return the deterministic target edge id when its endpoint exists.

## `target_entity_id` \{#agrag-common-data_models-candidate-CandidateRecord-target_entity_id}

```python
target_entity_id: UUID | None = None
```

## `target_label` \{#agrag-common-data_models-candidate-CandidateRecord-target_label}

```python
target_label: str | None = None
```

## `target_text` \{#agrag-common-data_models-candidate-CandidateRecord-target_text}

```python
target_text: str | None = None
```

## `text` \{#agrag-common-data_models-candidate-CandidateRecord-text}

```python
text: str = ''
```
