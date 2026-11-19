---
title: agrag.schema.loader.load_schema
sidebar_label: load_schema
---

# `agrag.schema.loader.load_schema` \{#agrag-schema-loader-load_schema}

```python
load_schema(source:SchemaSource, *, extends:SchemaSource | None = None) -> GraphSchema
```

Load a schema from any accepted source.

`source` may be a `GraphSchema`, a `Preset`, a dict, a list of entity
labels and relations, JSON text, a path to a `.json`, `.yaml`, `.yml`
or `.ttl` file, a Pydantic class or a list of Pydantic classes, or the
name of a shipped schema. Turtle (`.ttl`) import needs the optional
`schema-formats` extra. Shorthand is accepted at every level. The
result is always the canonical `GraphSchema`.

The shipped names are `"default"`, `"operations"` and `"legal"`. A
preset name or a `Preset` value means that preset applied to the default
schema, so `"operations"` is the schema named `default+operations`.

A schema with no `extends` stands alone and replaces the default schema.
With `extends`, the schema builds on a base. A type or relation that the
base already defines is an error unless it is marked `override: true`,
and an override may not loosen the base. `exclude` removes base types or
relations, with the patterns that use them. `add_patterns` adds pairs to
a base relation.

Extraction settings such as thresholds are not part of a schema. A key that
names one is an error.

**Parameters:**

- **source** (<code>[SchemaSource](SchemaSource.md)</code>) – The schema to load.
- **extends** (<code>[SchemaSource](SchemaSource.md) | None</code>) – The base schema, as a shipped name, a `Preset`, a path, a
  dict or a `GraphSchema`. A preset is applied to the default
  schema. Do not also set `extends` in `source`.

**Returns:**

- <code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code> – The loaded schema. `name` defaults to `custom` (the file stem for a
  file) and `version` defaults to `"1"`.

**Raises:**

- <code>[SchemaLoadError](../errors/SchemaLoadError.md)</code> – The source cannot be read or is invalid. The message
  lists every problem with the path to the offending key.
