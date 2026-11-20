---
title: agrag.common.data_models.index_record.IndexInfo
sidebar_label: IndexInfo
---

# `agrag.common.data_models.index_record.IndexInfo` \{#agrag-common-data_models-index_record-IndexInfo}

```python
IndexInfo(name:str, state:str, population_percent:float | None, type:str, labels:list[str], properties:list[str], dimensions:int | None = None) -> None
```

One search or lookup index in the graph database.

**Attributes:**

- [**name**](#agrag-common-data_models-index_record-IndexInfo-name) (<code>str</code>) – The index name. Backends that do not name indexes derive the same
  deterministic name that `vector_index_name` and
  `fulltext_index_name` build.
- [**state**](#agrag-common-data_models-index_record-IndexInfo-state) (<code>str</code>) – `ONLINE` when queries can use the index. Any other value means
  the index is still being built or has failed.
- [**population_percent**](#agrag-common-data_models-index_record-IndexInfo-population_percent) (<code>float | None</code>) – How much of the index is built, from 0 to 100. None
  when the backend does not report progress.
- [**type**](#agrag-common-data_models-index_record-IndexInfo-type) (<code>str</code>) – `VECTOR`, `FULLTEXT`, or another backend index type.
- [**labels**](#agrag-common-data_models-index_record-IndexInfo-labels) (<code>list\[str\]</code>) – The node labels or relationship types the index covers.
- [**properties**](#agrag-common-data_models-index_record-IndexInfo-properties) (<code>list\[str\]</code>) – The indexed property names.
- [**dimensions**](#agrag-common-data_models-index_record-IndexInfo-dimensions) (<code>int | None</code>) – The embedding size of a `VECTOR` index, otherwise None.

## `dimensions` \{#agrag-common-data_models-index_record-IndexInfo-dimensions}

```python
dimensions: int | None = None
```

## `labels` \{#agrag-common-data_models-index_record-IndexInfo-labels}

```python
labels: list[str]
```

## `name` \{#agrag-common-data_models-index_record-IndexInfo-name}

```python
name: str
```

## `population_percent` \{#agrag-common-data_models-index_record-IndexInfo-population_percent}

```python
population_percent: float | None
```

## `properties` \{#agrag-common-data_models-index_record-IndexInfo-properties}

```python
properties: list[str]
```

## `state` \{#agrag-common-data_models-index_record-IndexInfo-state}

```python
state: str
```

## `type` \{#agrag-common-data_models-index_record-IndexInfo-type}

```python
type: str
```
