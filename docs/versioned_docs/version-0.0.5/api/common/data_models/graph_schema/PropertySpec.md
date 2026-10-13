---
title: agrag.common.data_models.graph_schema.PropertySpec
sidebar_label: PropertySpec
---

# `agrag.common.data_models.graph_schema.PropertySpec` \{#agrag-common-data_models-graph_schema-PropertySpec}

Bases: <code>BaseModel</code>

The declaration of one property on an entity type.

A spec describes the property but does not validate extracted values.

**Attributes:**

- [**type**](#agrag-common-data_models-graph_schema-PropertySpec-type) (<code>[PropertyType](PropertyType.md)</code>) – The value type: `string`, `integer`, `float`, `boolean` or
  `date`.
- [**required**](#agrag-common-data_models-graph_schema-PropertySpec-required) (<code>bool</code>) – Whether an entity of this type should carry the property.
- [**enum**](#agrag-common-data_models-graph_schema-PropertySpec-enum) (<code>list\[str\] | None</code>) – Allowed values as text, or None for no restriction. Each value
  must be a valid text form of `type`.
- [**description**](#agrag-common-data_models-graph_schema-PropertySpec-description) (<code>str</code>) – Guidance for the extractor. Empty when there is none.

**Functions:**

- [**describe**](#agrag-common-data_models-graph_schema-PropertySpec-describe) – Render this property as one prompt phrase.

## `describe` \{#agrag-common-data_models-graph_schema-PropertySpec-describe}

```python
describe(name:str) -> str
```

Render this property as one prompt phrase.

## `description` \{#agrag-common-data_models-graph_schema-PropertySpec-description}

```python
description: str = ''
```

## `enum` \{#agrag-common-data_models-graph_schema-PropertySpec-enum}

```python
enum: list[str] | None = None
```

## `model_config` \{#agrag-common-data_models-graph_schema-PropertySpec-model_config}

```python
model_config = ConfigDict(extra='forbid')
```

## `required` \{#agrag-common-data_models-graph_schema-PropertySpec-required}

```python
required: bool = False
```

## `type` \{#agrag-common-data_models-graph_schema-PropertySpec-type}

```python
type: PropertyType
```
