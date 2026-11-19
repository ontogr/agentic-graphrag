---
title: agrag.ingestion.stats.dropped.DroppedCount
sidebar_label: DroppedCount
---

# `agrag.ingestion.stats.dropped.DroppedCount` \{#agrag-ingestion-stats-dropped-DroppedCount}

Bases: <code>BaseModel</code>

Count items removed by one rule for one label.

**Attributes:**

- [**kind**](#agrag-ingestion-stats-dropped-DroppedCount-kind) (<code>[DroppedKind](../../../common/data_models/dropped/DroppedKind.md)</code>) – Whether the item was an entity, relation or property.
- [**label**](#agrag-ingestion-stats-dropped-DroppedCount-label) (<code>str</code>) – The entity label, relation label or property key.
- [**reason**](#agrag-ingestion-stats-dropped-DroppedCount-reason) (<code>[DroppedReason](../../../common/data_models/dropped/DroppedReason.md)</code>) – The rule that removed the item.
- [**count**](#agrag-ingestion-stats-dropped-DroppedCount-count) (<code>int</code>) – The number of items removed.
- [**chunk_id**](#agrag-ingestion-stats-dropped-DroppedCount-chunk_id) (<code>UUID | None</code>) – The source chunk when the count belongs to one extraction.

## `chunk_id` \{#agrag-ingestion-stats-dropped-DroppedCount-chunk_id}

```python
chunk_id: UUID | None = None
```

## `count` \{#agrag-ingestion-stats-dropped-DroppedCount-count}

```python
count: int = Field(gt=0)
```

## `kind` \{#agrag-ingestion-stats-dropped-DroppedCount-kind}

```python
kind: DroppedKind
```

## `label` \{#agrag-ingestion-stats-dropped-DroppedCount-label}

```python
label: str
```

## `reason` \{#agrag-ingestion-stats-dropped-DroppedCount-reason}

```python
reason: DroppedReason
```
