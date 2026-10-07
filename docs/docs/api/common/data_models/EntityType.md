---
title: agrag.common.data_models.EntityType
sidebar_label: EntityType
---

# `agrag.common.data_models.EntityType` \{#agrag-common-data_models-EntityType}

Bases: <code>BaseModel</code>

One kind of entity a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-EntityType-label) (<code>str</code>) – The node label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-EntityType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**properties**](#agrag-common-data_models-EntityType-properties) (<code>dict\[str, str\]</code>) – Property names mapped to a type name, such as `"str"` or
  `"date"`. `label` and `text` are rejected, since both are
  vector payload keys retrieval filtering and keyword search use.
- [**subtypes**](#agrag-common-data_models-EntityType-subtypes) (<code>list\[str\]</code>) – Labels that narrow this type. Empty when this type has no subtypes.

## `description` \{#agrag-common-data_models-EntityType-description}

```python
description: str
```

## `label` \{#agrag-common-data_models-EntityType-label}

```python
label: str
```

## `properties` \{#agrag-common-data_models-EntityType-properties}

```python
properties: dict[str, str] = Field(default_factory=dict)
```

## `subtypes` \{#agrag-common-data_models-EntityType-subtypes}

```python
subtypes: list[str] = Field(default_factory=list)
```
