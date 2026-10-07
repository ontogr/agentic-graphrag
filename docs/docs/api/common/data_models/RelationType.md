---
title: agrag.common.data_models.RelationType
sidebar_label: RelationType
---

# `agrag.common.data_models.RelationType` \{#agrag-common-data_models-RelationType}

Bases: <code>BaseModel</code>

One kind of relation a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-RelationType-label) (<code>str</code>) – The relation label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-RelationType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**patterns**](#agrag-common-data_models-RelationType-patterns) (<code>list\[tuple\[str, str\]\]</code>) – Valid (source_label, target_label) pairs for this relation. An
  extraction whose triple is not in this list is dropped at normalize time.

## `description` \{#agrag-common-data_models-RelationType-description}

```python
description: str
```

## `label` \{#agrag-common-data_models-RelationType-label}

```python
label: str
```

## `patterns` \{#agrag-common-data_models-RelationType-patterns}

```python
patterns: list[tuple[str, str]]
```
