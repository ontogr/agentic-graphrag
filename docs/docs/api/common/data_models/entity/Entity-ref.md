---
title: agrag.common.data_models.entity.Entity
sidebar_label: Entity
---

# `agrag.common.data_models.entity.Entity` \{#agrag-common-data_models-entity-Entity}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

A permanent mention-level node, never destroyed once written.

Each Entity is one raw record: exact-match accumulation only folds a
new mention into the existing node for its normalized name. Fuzzy,
embedding, and LLM matches never absorb a node; they persist as
MATCHES edges with a derived ResolvedEntity instead, so both raw
records and their relationships survive resolution.

**Attributes:**

- [**label**](#agrag-common-data_models-entity-Entity-label) (<code>str</code>) – The EntityType label this entity was resolved as.
- [**name**](#agrag-common-data_models-entity-Entity-name) (<code>str</code>) – The canonical resolved surface form — field-resolved the same
  way any property is, but kept as its own field rather than
  inside properties, since every entity has one regardless of
  EntityType.properties' schema, and it is what gets embedded
  (embedding_text).
- [**properties**](#agrag-common-data_models-entity-Entity-properties) (<code>dict\[str, object\]</code>) – Field-resolved property values, keyed by the schema's
  declared property names (e.g. "dosage", "description" — whatever
  EntityType.properties for this label declares). Never holds name.
- [**embedding**](#agrag-common-data_models-entity-Entity-embedding) (<code>list\[float\] | None</code>) – The entity's dense vector, once populated by the storage
  stage. None before that point.
- [**merge_count**](#agrag-common-data_models-entity-Entity-merge_count) (<code>int</code>) – The total number of source mentions this entity's data
  was assembled from. Starts at 1.
- [**source_chunk_ids**](#agrag-common-data_models-entity-Entity-source_chunk_ids) (<code>list\[UUID\]</code>) – Ids of every Chunk a mention contributing to this
  entity's data came from. Each also backs one MENTIONED_IN edge
  from that Chunk to this Entity.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-entity-Entity-to_node_record) – Return this entity as a GraphStore write record.

## `created_at` \{#agrag-common-data_models-entity-Entity-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `embedding` \{#agrag-common-data_models-entity-Entity-embedding}

```python
embedding: list[float] | None = None
```

## `embedding_text` \{#agrag-common-data_models-entity-Entity-embedding_text}

```python
embedding_text: str
```

Return the text this entity's embedding is computed from.

Name alone, or name plus a "description" property when the schema
declares one — decided once, here, so every embedding call site
(resolution's future embedding tier, storage-stage population,
Graph.consolidate()) embeds the same text for the same entity.

## `id` \{#agrag-common-data_models-entity-Entity-id}

```python
id: UUID
```

## `label` \{#agrag-common-data_models-entity-Entity-label}

```python
label: str
```

## `merge_count` \{#agrag-common-data_models-entity-Entity-merge_count}

```python
merge_count: int = 1
```

## `merge_key` \{#agrag-common-data_models-entity-Entity-merge_key}

```python
merge_key: str
```

Return this entity's global exact-match lookup key.

(label, normalized name) — the same identity ExactMatch already uses
in-batch, applied to a persisted store lookup. A derived value, not
stored redundantly anywhere else on this model; to_node_record()
computes it fresh from label/name every write, so it can never drift
from what the fields it's derived from actually say.

## `metadata` \{#agrag-common-data_models-entity-Entity-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `name` \{#agrag-common-data_models-entity-Entity-name}

```python
name: str
```

## `properties` \{#agrag-common-data_models-entity-Entity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

## `source_chunk_ids` \{#agrag-common-data_models-entity-Entity-source_chunk_ids}

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

## `to_node_record` \{#agrag-common-data_models-entity-Entity-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this entity as a GraphStore write record.

Name, merge_key, merge_count, and source_chunk_ids are
flattened into properties as plain JSON-safe values; GraphStore has
no reason to know these fields are special.
