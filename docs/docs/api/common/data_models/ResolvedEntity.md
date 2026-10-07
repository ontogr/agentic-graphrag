---
title: agrag.common.data_models.ResolvedEntity
sidebar_label: ResolvedEntity
---

# `agrag.common.data_models.ResolvedEntity` \{#agrag-common-data_models-ResolvedEntity}

Bases: <code>[DataPoint](data_point/DataPoint.md)</code>

A cluster of entities that refer to the same thing.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-ResolvedEntity-to_node_record) – Return this resolved entity as a graph write record.

**Attributes:**

- [**created_at**](#agrag-common-data_models-ResolvedEntity-created_at) (<code>datetime</code>) –
- [**embedding**](#agrag-common-data_models-ResolvedEntity-embedding) (<code>list\[float\] | None</code>) –
- [**embedding_text**](#agrag-common-data_models-ResolvedEntity-embedding_text) (<code>str</code>) – Return the text used to embed this resolved entity.
- [**id**](#agrag-common-data_models-ResolvedEntity-id) (<code>UUID</code>) –
- [**label**](#agrag-common-data_models-ResolvedEntity-label) (<code>str</code>) –
- [**member_ids**](#agrag-common-data_models-ResolvedEntity-member_ids) (<code>list\[UUID\]</code>) –
- [**metadata**](#agrag-common-data_models-ResolvedEntity-metadata) (<code>dict\[str, Any\]</code>) –
- [**name**](#agrag-common-data_models-ResolvedEntity-name) (<code>str</code>) –
- [**properties**](#agrag-common-data_models-ResolvedEntity-properties) (<code>dict\[str, object\]</code>) –
- [**vector_sync_error**](#agrag-common-data_models-ResolvedEntity-vector_sync_error) (<code>str | None</code>) –
- [**vector_sync_status**](#agrag-common-data_models-ResolvedEntity-vector_sync_status) (<code>Literal['pending', 'synced', 'failed']</code>) –

## `created_at` \{#agrag-common-data_models-ResolvedEntity-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `embedding` \{#agrag-common-data_models-ResolvedEntity-embedding}

```python
embedding: list[float] | None = None
```

## `embedding_text` \{#agrag-common-data_models-ResolvedEntity-embedding_text}

```python
embedding_text: str
```

Return the text used to embed this resolved entity.

## `id` \{#agrag-common-data_models-ResolvedEntity-id}

```python
id: UUID
```

## `label` \{#agrag-common-data_models-ResolvedEntity-label}

```python
label: str
```

## `member_ids` \{#agrag-common-data_models-ResolvedEntity-member_ids}

```python
member_ids: list[UUID] = Field(default_factory=list)
```

## `metadata` \{#agrag-common-data_models-ResolvedEntity-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `name` \{#agrag-common-data_models-ResolvedEntity-name}

```python
name: str
```

## `properties` \{#agrag-common-data_models-ResolvedEntity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

## `to_node_record` \{#agrag-common-data_models-ResolvedEntity-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this resolved entity as a graph write record.

## `vector_sync_error` \{#agrag-common-data_models-ResolvedEntity-vector_sync_error}

```python
vector_sync_error: str | None = None
```

## `vector_sync_status` \{#agrag-common-data_models-ResolvedEntity-vector_sync_status}

```python
vector_sync_status: Literal['pending', 'synced', 'failed'] = 'pending'
```
