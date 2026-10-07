---
title: agrag.common.data_models.graph_schema.GraphSchema
sidebar_label: GraphSchema
---

# `agrag.common.data_models.graph_schema.GraphSchema` \{#agrag-common-data_models-graph_schema-GraphSchema}

Bases: <code>BaseModel</code>

A versioned contract of entity and relation types.

Every extraction call is validated against a GraphSchema; there is no schema-free
extraction path. Round-trip with `model_dump(mode="json")`/`model_validate()`.
A schema declaring an entity property name the vector payload reserves fails that
validation, so a payload written before the check existed must be migrated before
it loads again. See `EntityType.properties`.

**Attributes:**

- [**name**](#agrag-common-data_models-graph_schema-GraphSchema-name) (<code>str</code>) – A short, unique name for this schema.
- [**version**](#agrag-common-data_models-graph_schema-GraphSchema-version) (<code>str</code>) – The schema version. Bump when types or patterns change.
- [**entities**](#agrag-common-data_models-graph_schema-GraphSchema-entities) (<code>list\[[EntityType](EntityType.md)\]</code>) – The entity types this schema recognizes.
- [**relations**](#agrag-common-data_models-graph_schema-GraphSchema-relations) (<code>list\[[RelationType](RelationType.md)\]</code>) – The relation types this schema recognizes.

**Functions:**

- [**to_compact_summary**](#agrag-common-data_models-graph_schema-GraphSchema-to_compact_summary) – Serialize only entity labels and relation patterns for a prompt.
- [**to_prompt_description**](#agrag-common-data_models-graph_schema-GraphSchema-to_prompt_description) – Serialize this schema in full for an LLM prompt.

## `entities` \{#agrag-common-data_models-graph_schema-GraphSchema-entities}

```python
entities: list[EntityType]
```

## `name` \{#agrag-common-data_models-graph_schema-GraphSchema-name}

```python
name: str
```

## `relations` \{#agrag-common-data_models-graph_schema-GraphSchema-relations}

```python
relations: list[RelationType]
```

## `to_compact_summary` \{#agrag-common-data_models-graph_schema-GraphSchema-to_compact_summary}

```python
to_compact_summary() -> str
```

Serialize only entity labels and relation patterns for a prompt.

Descriptions, properties, and subtypes are omitted, so this is the
shape to inject where prompt space is tight.
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

Every entity type's label, description, declared properties, and
subtypes are listed, followed by every relation type's label,
description, and valid (source, target) patterns. Use
`to_compact_summary` instead when prompt space is tight.

**Returns:**

- <code>str</code> – A plain-text schema description, one fact per line.

## `version` \{#agrag-common-data_models-graph_schema-GraphSchema-version}

```python
version: str
```
