---
title: agrag.common.data_models.query_value.QueryValue
sidebar_label: QueryValue
---

# `agrag.common.data_models.query_value.QueryValue` \{#agrag-common-data_models-query_value-QueryValue}

Bases: <code>BaseModel</code>

One result row returned by a generated graph query.

**Attributes:**

- [**id**](#agrag-common-data_models-query_value-QueryValue-id) (<code>UUID</code>) –
- [**value**](#agrag-common-data_models-query_value-QueryValue-value) (<code>Any</code>) –

## `id` \{#agrag-common-data_models-query_value-QueryValue-id}

```python
id: UUID = Field(default_factory=uuid4)
```

## `value` \{#agrag-common-data_models-query_value-QueryValue-value}

```python
value: Any
```
