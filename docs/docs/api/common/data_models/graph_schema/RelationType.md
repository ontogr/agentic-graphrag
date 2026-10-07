---
title: agrag.common.data_models.graph_schema.RelationType
sidebar_label: RelationType
---

# `agrag.common.data_models.graph_schema.RelationType` \{#agrag-common-data_models-graph_schema-RelationType}

Bases: <code>BaseModel</code>

One kind of relation a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-graph_schema-RelationType-label) (<code>str</code>) – The relation label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-graph_schema-RelationType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**patterns**](#agrag-common-data_models-graph_schema-RelationType-patterns) (<code>list\[tuple\[str, str\]\]</code>) – Valid (source_label, target_label) pairs for this relation. An
  extraction whose triple is not in this list is dropped at normalize time.

## `description` \{#agrag-common-data_models-graph_schema-RelationType-description}

```python
description: str
```

## `label` \{#agrag-common-data_models-graph_schema-RelationType-label}

```python
label: str
```

## `patterns` \{#agrag-common-data_models-graph_schema-RelationType-patterns}

```python
patterns: list[tuple[str, str]]
```
