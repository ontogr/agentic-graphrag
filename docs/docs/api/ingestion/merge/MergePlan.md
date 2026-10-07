---
title: agrag.ingestion.merge.MergePlan
sidebar_label: MergePlan
---

# `agrag.ingestion.merge.MergePlan` \{#agrag-ingestion-merge-MergePlan}

Bases: <code>BaseModel</code>

Computed result of merging zero or more entities and mentions.

**Attributes:**

- [**survivor**](#agrag-ingestion-merge-MergePlan-survivor) (<code>[Entity](../../common/data_models/entity/Entity-ref.md)</code>) – The resulting Entity. Its merge_count and
  source_chunk_ids are this call's best local computation, for
  reporting. apply_merge writes new_source_chunk_ids and
  merge_count_delta atomically instead, so a concurrent writer's
  own contribution to the same node is never overwritten.
- [**conflicts**](#agrag-ingestion-merge-MergePlan-conflicts) (<code>list\[[ConflictRecord](ConflictRecord.md)\]</code>) – Every field that had more than one candidate value.
- [**accepted_merge_keys**](#agrag-ingestion-merge-MergePlan-accepted_merge_keys) (<code>list\[str\]</code>) – Every normalized merge_key this merge
  accepted, from existing_entities and mentions alike, not only
  the survivor's own chosen name. A later mention of any
  accepted name resolves back to this entity instead of creating
  a duplicate.
- [**new_source_chunk_ids**](#agrag-ingestion-merge-MergePlan-new_source_chunk_ids) (<code>list\[UUID\]</code>) – The chunk ids this call's mentions contribute,
  applied as an atomic union against whatever the survivor's node
  currently has.
- [**merge_count_delta**](#agrag-ingestion-merge-MergePlan-merge_count_delta) (<code>int</code>) – The amount to atomically add to whatever
  merge_count the survivor's node currently has.

## `accepted_merge_keys` \{#agrag-ingestion-merge-MergePlan-accepted_merge_keys}

```python
accepted_merge_keys: list[str] = []
```

## `conflicts` \{#agrag-ingestion-merge-MergePlan-conflicts}

```python
conflicts: list[ConflictRecord] = []
```

## `merge_count_delta` \{#agrag-ingestion-merge-MergePlan-merge_count_delta}

```python
merge_count_delta: int = 0
```

## `new_source_chunk_ids` \{#agrag-ingestion-merge-MergePlan-new_source_chunk_ids}

```python
new_source_chunk_ids: list[UUID] = []
```

## `survivor` \{#agrag-ingestion-merge-MergePlan-survivor}

```python
survivor: Entity
```
