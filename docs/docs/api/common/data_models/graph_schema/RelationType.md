---
title: agrag.common.data_models.graph_schema.RelationType
sidebar_label: RelationType
---

# `agrag.common.data_models.graph_schema.RelationType` \{#agrag-common-data_models-graph_schema-RelationType}

Bases: <code>BaseModel</code>

One kind of relation a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-graph_schema-RelationType-label) (<code>str</code>) – The relation label used in the extraction prompt and the graph.
  It must not be a relationship type the graph writes itself.
- [**description**](#agrag-common-data_models-graph_schema-RelationType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**patterns**](#agrag-common-data_models-graph_schema-RelationType-patterns) (<code>list\[tuple\[str, str\]\]</code>) – Valid (source_label, target_label) pairs. A pattern also covers
  children of its endpoint types.
- [**cardinality**](#agrag-common-data_models-graph_schema-RelationType-cardinality) (<code>[Cardinality](Cardinality.md)</code>) – Optional edge limits on each side.
- [**symmetric**](#agrag-common-data_models-graph_schema-RelationType-symmetric) (<code>bool</code>) – Whether each allowed edge is allowed in reverse too.

## `cardinality` \{#agrag-common-data_models-graph_schema-RelationType-cardinality}

```python
cardinality: Cardinality = Field(default_factory=Cardinality)
```

## `description` \{#agrag-common-data_models-graph_schema-RelationType-description}

```python
description: str
```

## `label` \{#agrag-common-data_models-graph_schema-RelationType-label}

```python
label: str
```

## `model_config` \{#agrag-common-data_models-graph_schema-RelationType-model_config}

```python
model_config = ConfigDict(extra='forbid')
```

## `patterns` \{#agrag-common-data_models-graph_schema-RelationType-patterns}

```python
patterns: list[tuple[str, str]]
```

## `symmetric` \{#agrag-common-data_models-graph_schema-RelationType-symmetric}

```python
symmetric: bool = False
```
