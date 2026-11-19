---
title: agrag.common.data_models.evidence.SourceIndexStatus
sidebar_label: SourceIndexStatus
---

# `agrag.common.data_models.evidence.SourceIndexStatus` \{#agrag-common-data_models-evidence-SourceIndexStatus}

Bases: <code>BaseModel</code>

The state and population progress of one search index.

**Attributes:**

- [**name**](#agrag-common-data_models-evidence-SourceIndexStatus-name) (<code>str</code>) – Database index name.
- [**state**](#agrag-common-data_models-evidence-SourceIndexStatus-state) (<code>str</code>) – Database state such as `ONLINE`, `POPULATING`, or `FAILED`.
- [**population_percent**](#agrag-common-data_models-evidence-SourceIndexStatus-population_percent) (<code>float | None</code>) – Population progress, or None when unavailable.

## `name` \{#agrag-common-data_models-evidence-SourceIndexStatus-name}

```python
name: str
```

## `population_percent` \{#agrag-common-data_models-evidence-SourceIndexStatus-population_percent}

```python
population_percent: float | None = None
```

## `state` \{#agrag-common-data_models-evidence-SourceIndexStatus-state}

```python
state: str
```
