---
title: agrag.common.data_models.vector_record.VectorRepairCounts
sidebar_label: VectorRepairCounts
---

# `agrag.common.data_models.vector_record.VectorRepairCounts` \{#agrag-common-data_models-vector_record-VectorRepairCounts}

Bases: <code>BaseModel</code>

Repair counts and failures for one collection.

**Attributes:**

- [**checked**](#agrag-common-data_models-vector_record-VectorRepairCounts-checked) (<code>int</code>) – Committed graph nodes considered.
- [**missing**](#agrag-common-data_models-vector_record-VectorRepairCounts-missing) (<code>int</code>) – Graph nodes without a stored vector.
- [**upserted**](#agrag-common-data_models-vector_record-VectorRepairCounts-upserted) (<code>int</code>) – Missing vectors successfully written.
- [**pruned**](#agrag-common-data_models-vector_record-VectorRepairCounts-pruned) (<code>int</code>) – Orphan vectors removed when pruning was requested.
- [**failures**](#agrag-common-data_models-vector_record-VectorRepairCounts-failures) (<code>list\[[StageFailure](../stage_failure/StageFailure.md)\]</code>) – Embedding or storage failures that require another repair.

## `checked` \{#agrag-common-data_models-vector_record-VectorRepairCounts-checked}

```python
checked: int = 0
```

## `failures` \{#agrag-common-data_models-vector_record-VectorRepairCounts-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `missing` \{#agrag-common-data_models-vector_record-VectorRepairCounts-missing}

```python
missing: int = 0
```

## `pruned` \{#agrag-common-data_models-vector_record-VectorRepairCounts-pruned}

```python
pruned: int = 0
```

## `upserted` \{#agrag-common-data_models-vector_record-VectorRepairCounts-upserted}

```python
upserted: int = 0
```
