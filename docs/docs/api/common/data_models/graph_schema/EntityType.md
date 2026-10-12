---
title: agrag.common.data_models.graph_schema.EntityType
sidebar_label: EntityType
---

# `agrag.common.data_models.graph_schema.EntityType` \{#agrag-common-data_models-graph_schema-EntityType}

Bases: <code>BaseModel</code>

One kind of entity a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-graph_schema-EntityType-label) (<code>str</code>) – The node label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-graph_schema-EntityType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**parents**](#agrag-common-data_models-graph_schema-EntityType-parents) (<code>list\[str\]</code>) – Declared parent labels, nearest parent first.
- [**properties**](#agrag-common-data_models-graph_schema-EntityType-properties) (<code>dict\[str, [PropertySpec](PropertySpec.md)\]</code>) – Property names mapped to their `PropertySpec`. Properties
  are not inherited from parents. `label`, `text` and the keys
  the graph writes itself (`id`, `name`, `merge_key`,
  `merge_count`, `source_chunk_ids`, `created_at`,
  `embedding`) are rejected as names.

## `description` \{#agrag-common-data_models-graph_schema-EntityType-description}

```python
description: str
```

## `label` \{#agrag-common-data_models-graph_schema-EntityType-label}

```python
label: str
```

## `model_config` \{#agrag-common-data_models-graph_schema-EntityType-model_config}

```python
model_config = ConfigDict(extra='forbid')
```

## `parents` \{#agrag-common-data_models-graph_schema-EntityType-parents}

```python
parents: list[str] = Field(default_factory=list)
```

## `properties` \{#agrag-common-data_models-graph_schema-EntityType-properties}

```python
properties: dict[str, PropertySpec] = Field(default_factory=dict)
```
