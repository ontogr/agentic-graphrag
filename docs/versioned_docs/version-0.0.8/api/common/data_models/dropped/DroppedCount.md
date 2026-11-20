---
title: agrag.common.data_models.dropped.DroppedCount
sidebar_label: DroppedCount
---

# `agrag.common.data_models.dropped.DroppedCount` \{#agrag-common-data_models-dropped-DroppedCount}

Bases: <code>BaseModel</code>

Count items removed by one rule for one label.

**Attributes:**

- [**kind**](#agrag-common-data_models-dropped-DroppedCount-kind) (<code>[DroppedKind](DroppedKind.md)</code>) – Whether the item was an entity, relation or property.
- [**label**](#agrag-common-data_models-dropped-DroppedCount-label) (<code>str</code>) – The entity label, relation label or property key.
- [**reason**](#agrag-common-data_models-dropped-DroppedCount-reason) (<code>[DroppedReason](DroppedReason.md)</code>) – The rule that removed the item.
- [**count**](#agrag-common-data_models-dropped-DroppedCount-count) (<code>int</code>) – The number of items removed.
- [**chunk_id**](#agrag-common-data_models-dropped-DroppedCount-chunk_id) (<code>UUID | None</code>) – The source chunk when the count belongs to one extraction.

## `chunk_id` \{#agrag-common-data_models-dropped-DroppedCount-chunk_id}

```python
chunk_id: UUID | None = None
```

## `count` \{#agrag-common-data_models-dropped-DroppedCount-count}

```python
count: int = Field(gt=0)
```

## `kind` \{#agrag-common-data_models-dropped-DroppedCount-kind}

```python
kind: DroppedKind
```

## `label` \{#agrag-common-data_models-dropped-DroppedCount-label}

```python
label: str
```

## `reason` \{#agrag-common-data_models-dropped-DroppedCount-reason}

```python
reason: DroppedReason
```
