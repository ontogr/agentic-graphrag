---
title: agrag.common.data_models.graph_schema.GraphSchema
sidebar_label: GraphSchema
---

# `agrag.common.data_models.graph_schema.GraphSchema` \{#agrag-common-data_models-graph_schema-GraphSchema}

Bases: <code>BaseModel</code>

A versioned contract of entity and relation types.

Every extraction call is validated against a GraphSchema. There is no
schema-free extraction path. Round-trip with
`model_dump(mode="json")` and `model_validate()`. A schema declaring
an entity property name that the vector payload reserves fails that
validation. See `EntityType.properties`.

Construct a new schema to change its types. Ancestor access revalidates the
hierarchy so direct parent edits cannot cause an invalid traversal.

**Attributes:**

- [**name**](#agrag-common-data_models-graph_schema-GraphSchema-name) (<code>str</code>) – A short, unique name for this schema.
- [**version**](#agrag-common-data_models-graph_schema-GraphSchema-version) (<code>str</code>) – The schema version. Bump when types or patterns change.
- [**entities**](#agrag-common-data_models-graph_schema-GraphSchema-entities) (<code>list\[[EntityType](EntityType.md)\]</code>) – The entity types this schema recognizes.
- [**relations**](#agrag-common-data_models-graph_schema-GraphSchema-relations) (<code>list\[[RelationType](RelationType.md)\]</code>) – The relation types this schema recognizes.

**Functions:**

- [**allows**](#agrag-common-data_models-graph_schema-GraphSchema-allows) – Return whether a pair of entity types is allowed for a relation.
- [**ancestors**](#agrag-common-data_models-graph_schema-GraphSchema-ancestors) – Return an entity type's ancestors in nearest-first breadth-first order.
- [**node_labels**](#agrag-common-data_models-graph_schema-GraphSchema-node_labels) – Return a node's leaf label followed by its ancestors.
- [**resolve**](#agrag-common-data_models-graph_schema-GraphSchema-resolve) – Render entity details and relation patterns expanded over child types.
- [**to_compact_summary**](#agrag-common-data_models-graph_schema-GraphSchema-to_compact_summary) – Serialize entity labels, parents and relation patterns for a prompt.
- [**to_prompt_description**](#agrag-common-data_models-graph_schema-GraphSchema-to_prompt_description) – Serialize this schema in full for an LLM prompt.

## `allows` \{#agrag-common-data_models-graph_schema-GraphSchema-allows}

```python
allows(relation:str, source_label:str, target_label:str) -> bool
```

Return whether a pair of entity types is allowed for a relation.

Patterns cover descendants, and symmetric relations accept reversal.
Unknown entity or relation labels return False.
Invalid parent edits raise ValueError rather than traversing bad data.

**Parameters:**

- **relation** (<code>str</code>) – The relation label.
- **source_label** (<code>str</code>) – The source entity's leaf label.
- **target_label** (<code>str</code>) – The target entity's leaf label.

## `ancestors` \{#agrag-common-data_models-graph_schema-GraphSchema-ancestors}

```python
ancestors(label:str) -> list[str]
```

Return an entity type's ancestors in nearest-first breadth-first order.

Parents retain their listed order. Shared ancestors appear only once.

**Parameters:**

- **label** (<code>str</code>) – A declared entity label.

**Raises:**

- <code>ValueError</code> – If the label is not declared or the hierarchy is invalid.

## `entities` \{#agrag-common-data_models-graph_schema-GraphSchema-entities}

```python
entities: list[EntityType]
```

## `model_config` \{#agrag-common-data_models-graph_schema-GraphSchema-model_config}

```python
model_config = ConfigDict(extra='forbid')
```

## `name` \{#agrag-common-data_models-graph_schema-GraphSchema-name}

```python
name: str
```

## `node_labels` \{#agrag-common-data_models-graph_schema-GraphSchema-node_labels}

```python
node_labels(label:str) -> list[str]
```

Return a node's leaf label followed by its ancestors.

**Parameters:**

- **label** (<code>str</code>) – A declared entity label.

**Raises:**

- <code>ValueError</code> – If the label is not declared or the hierarchy is invalid.

## `relations` \{#agrag-common-data_models-graph_schema-GraphSchema-relations}

```python
relations: list[RelationType]
```

## `resolve` \{#agrag-common-data_models-graph_schema-GraphSchema-resolve}

```python
resolve() -> str
```

Render entity details and relation patterns expanded over child types.

The final line counts entity and relation labels.

## `to_compact_summary` \{#agrag-common-data_models-graph_schema-GraphSchema-to_compact_summary}

```python
to_compact_summary() -> str
```

Serialize entity labels, parents and relation patterns for a prompt.

Descriptions, properties and cardinality limits are omitted, so this is
the shape to inject where prompt space is tight.
`to_prompt_description` carries the same labels with their
full detail.

**Returns:**

- <code>str</code> – A plain-text summary of entity labels and valid relation
- <code>str</code> – patterns.

## `to_prompt_description` \{#agrag-common-data_models-graph_schema-GraphSchema-to_prompt_description}

```python
to_prompt_description() -> str
```

Serialize this schema in full for an LLM prompt.

Entity labels, parents and declared properties are followed by each
relation's valid patterns, symmetry and cardinality. Use
`to_compact_summary` instead when prompt space is tight.

**Returns:**

- <code>str</code> – A plain-text schema description, one fact per line.

## `version` \{#agrag-common-data_models-graph_schema-GraphSchema-version}

```python
version: str
```
