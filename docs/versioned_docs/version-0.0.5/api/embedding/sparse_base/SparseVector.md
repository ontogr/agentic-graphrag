---
title: agrag.embedding.sparse_base.SparseVector
sidebar_label: SparseVector
---

# `agrag.embedding.sparse_base.SparseVector` \{#agrag-embedding-sparse_base-SparseVector}

Bases: <code>BaseModel</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag-embedding-sparse_base-SparseVector-indices) (<code>list\[int\]</code>) – The positions of nonzero entries.
- [**values**](#agrag-embedding-sparse_base-SparseVector-values) (<code>list\[float\]</code>) – The weight at each index, aligned with `indices`.

## `indices` \{#agrag-embedding-sparse_base-SparseVector-indices}

```python
indices: list[int]
```

## `values` \{#agrag-embedding-sparse_base-SparseVector-values}

```python
values: list[float]
```
