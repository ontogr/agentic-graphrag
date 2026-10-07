---
title: agrag.common.data_models.relation.Relation
sidebar_label: Relation
---

# `agrag.common.data_models.relation.Relation` \{#agrag-common-data_models-relation-Relation}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

A resolved relationship between two Entity nodes.

**Attributes:**

- [**type**](#agrag-common-data_models-relation-Relation-type) (<code>str</code>) – The RelationType label this relationship was resolved as.
- [**source_id**](#agrag-common-data_models-relation-Relation-source_id) (<code>UUID</code>) – The id of the source Entity.
- [**target_id**](#agrag-common-data_models-relation-Relation-target_id) (<code>UUID</code>) – The id of the target Entity.
- [**properties**](#agrag-common-data_models-relation-Relation-properties) (<code>dict\[str, object\]</code>) – Field-resolved property values.
- [**source_chunk_ids**](#agrag-common-data_models-relation-Relation-source_chunk_ids) (<code>list\[UUID\]</code>) – Ids of every Chunk a mention contributing to this
  relationship came from. A relationship attested by more than one
  source has more than one id here, rather than existing as
  parallel edges.

**Functions:**

- [**to_relation_record**](#agrag-common-data_models-relation-Relation-to_relation_record) – Return this relationship as a GraphStore write record.

## `created_at` \{#agrag-common-data_models-relation-Relation-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `id` \{#agrag-common-data_models-relation-Relation-id}

```python
id: UUID
```

## `metadata` \{#agrag-common-data_models-relation-Relation-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `properties` \{#agrag-common-data_models-relation-Relation-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

## `source_chunk_ids` \{#agrag-common-data_models-relation-Relation-source_chunk_ids}

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

## `source_id` \{#agrag-common-data_models-relation-Relation-source_id}

```python
source_id: UUID
```

## `target_id` \{#agrag-common-data_models-relation-Relation-target_id}

```python
target_id: UUID
```

## `to_relation_record` \{#agrag-common-data_models-relation-Relation-to_relation_record}

```python
to_relation_record() -> RelationRecord
```

Return this relationship as a GraphStore write record.

## `type` \{#agrag-common-data_models-relation-Relation-type}

```python
type: str
```
