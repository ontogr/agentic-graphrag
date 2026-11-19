---
title: agrag.common.data_models.vector_record.CollectionInfo
sidebar_label: CollectionInfo
---

# `agrag.common.data_models.vector_record.CollectionInfo` \{#agrag-common-data_models-vector_record-CollectionInfo}

Bases: <code>BaseModel</code>

The dimensions, distance metric and record count of a collection.

**Attributes:**

- [**dimensions**](#agrag-common-data_models-vector_record-CollectionInfo-dimensions) (<code>int</code>) – Number of dense values in each vector.
- [**distance**](#agrag-common-data_models-vector_record-CollectionInfo-distance) (<code>[Distance](Distance.md)</code>) – Metric used for dense search.
- [**count**](#agrag-common-data_models-vector_record-CollectionInfo-count) (<code>int</code>) – Number of records stored in the collection. A store may report an
  estimate when the caller declines an exact count.

## `count` \{#agrag-common-data_models-vector_record-CollectionInfo-count}

```python
count: int
```

## `dimensions` \{#agrag-common-data_models-vector_record-CollectionInfo-dimensions}

```python
dimensions: int
```

## `distance` \{#agrag-common-data_models-vector_record-CollectionInfo-distance}

```python
distance: Distance
```
