---
title: agrag.common.data_models.vector_record.VectorWork
sidebar_label: VectorWork
---

# `agrag.common.data_models.vector_record.VectorWork` \{#agrag-common-data_models-vector_record-VectorWork}

Bases: <code>BaseModel</code>

Durable vector synchronization and deletion work after a graph commit.

**Attributes:**

- [**targets**](#agrag-common-data_models-vector_record-VectorWork-targets) (<code>list\[[VectorTarget](VectorTarget.md)\]</code>) – Committed nodes to re-embed from current graph text.
- [**deletes**](#agrag-common-data_models-vector_record-VectorWork-deletes) (<code>list\[[VectorTarget](VectorTarget.md)\]</code>) – Candidates to remove only if their graph nodes are absent.

## `deletes` \{#agrag-common-data_models-vector_record-VectorWork-deletes}

```python
deletes: list[VectorTarget] = Field(default_factory=list)
```

## `targets` \{#agrag-common-data_models-vector_record-VectorWork-targets}

```python
targets: list[VectorTarget] = Field(default_factory=list)
```
