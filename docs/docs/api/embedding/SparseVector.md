---
title: agrag.embedding.SparseVector
sidebar_label: SparseVector
---

# `agrag.embedding.SparseVector` \{#agrag-embedding-SparseVector}

Bases: <code>BaseModel</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag-embedding-SparseVector-indices) (<code>list\[int\]</code>) – The positions of nonzero entries.
- [**values**](#agrag-embedding-SparseVector-values) (<code>list\[float\]</code>) – The weight at each index, aligned with `indices`.

## `indices` \{#agrag-embedding-SparseVector-indices}

```python
indices: list[int]
```

## `values` \{#agrag-embedding-SparseVector-values}

```python
values: list[float]
```
