---
title: agrag.common.data_models.presets.Preset
sidebar_label: Preset
---

# `agrag.common.data_models.presets.Preset` \{#agrag-common-data_models-presets-Preset}

Bases: <code>BaseModel</code>

A curated set of entity types to add to a base schema.

A preset adds entity types. It never adds a relation, changes a pattern or
changes a description.

**Attributes:**

- [**name**](#agrag-common-data_models-presets-Preset-name) (<code>str</code>) – A short, unique name, such as `"operations"`.
- [**entities**](#agrag-common-data_models-presets-Preset-entities) (<code>list\[[EntityType](../graph_schema/EntityType.md)\]</code>) – The entity types the preset adds.
- [**widenings**](#agrag-common-data_models-presets-Preset-widenings) (<code>tuple[()]</code>) – Always empty in this release.

**Functions:**

- [**apply**](#agrag-common-data_models-presets-Preset-apply) – Return a new schema with this preset's entity types appended.

## `apply` \{#agrag-common-data_models-presets-Preset-apply}

```python
apply(base:GraphSchema) -> GraphSchema
```

Return a new schema with this preset's entity types appended.

**Parameters:**

- **base** (<code>[GraphSchema](../graph_schema/GraphSchema.md)</code>) – The schema to extend.

**Returns:**

- <code>[GraphSchema](../graph_schema/GraphSchema.md)</code> – A new schema named `"<base name>+<preset name>"` with the base
- <code>[GraphSchema](../graph_schema/GraphSchema.md)</code> – version and relations.

**Raises:**

- <code>ValueError</code> – The base already declares a preset entity label.

## `entities` \{#agrag-common-data_models-presets-Preset-entities}

```python
entities: list[EntityType]
```

## `model_config` \{#agrag-common-data_models-presets-Preset-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `name` \{#agrag-common-data_models-presets-Preset-name}

```python
name: str
```

## `widenings` \{#agrag-common-data_models-presets-Preset-widenings}

```python
widenings: tuple[()] = ()
```
