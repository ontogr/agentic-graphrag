---
title: agrag.common.data_models.graph_schema.Cardinality
sidebar_label: Cardinality
---

# `agrag.common.data_models.graph_schema.Cardinality` \{#agrag-common-data_models-graph_schema-Cardinality}

Bases: <code>BaseModel</code>

Declared limits on distinct endpoints of one relation, across its patterns.

Limits describe the schema but do not constrain extracted edges.

**Attributes:**

- [**max_per_source**](#agrag-common-data_models-graph_schema-Cardinality-max_per_source) (<code>int | None</code>) – Maximum targets per source. None means no limit.
- [**max_per_target**](#agrag-common-data_models-graph_schema-Cardinality-max_per_target) (<code>int | None</code>) – Maximum sources per target. None means no limit.

## `max_per_source` \{#agrag-common-data_models-graph_schema-Cardinality-max_per_source}

```python
max_per_source: int | None = Field(default=None, ge=1)
```

## `max_per_target` \{#agrag-common-data_models-graph_schema-Cardinality-max_per_target}

```python
max_per_target: int | None = Field(default=None, ge=1)
```

## `model_config` \{#agrag-common-data_models-graph_schema-Cardinality-model_config}

```python
model_config = ConfigDict(extra='forbid')
```
