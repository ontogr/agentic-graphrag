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
- [**properties**](#agrag-common-data_models-graph_schema-EntityType-properties) (<code>dict\[str, str\]</code>) – Property names mapped to a type name, such as `"str"` or
  `"date"`. `label` and `text` are rejected, because retrieval
  filtering and keyword search use both as vector payload keys.
- [**subtypes**](#agrag-common-data_models-graph_schema-EntityType-subtypes) (<code>list\[str\]</code>) – Labels that narrow this type. Empty when this type has no subtypes.

## `description` \{#agrag-common-data_models-graph_schema-EntityType-description}

```python
description: str
```

## `label` \{#agrag-common-data_models-graph_schema-EntityType-label}

```python
label: str
```

## `properties` \{#agrag-common-data_models-graph_schema-EntityType-properties}

```python
properties: dict[str, str] = Field(default_factory=dict)
```

## `subtypes` \{#agrag-common-data_models-graph_schema-EntityType-subtypes}

```python
subtypes: list[str] = Field(default_factory=list)
```
