---
title: agrag.schema.formats.result.ImportResult
sidebar_label: ImportResult
---

# `agrag.schema.formats.result.ImportResult` \{#agrag-schema-formats-result-ImportResult}

```python
ImportResult(schema:GraphSchema, warnings:list[FormatWarning] = list()) -> None
```

A schema read from another format, with everything the read lost.

**Attributes:**

- [**schema**](#agrag-schema-formats-result-ImportResult-schema) (<code>[GraphSchema](../../../common/data_models/graph_schema/GraphSchema.md)</code>) – The imported schema.
- [**warnings**](#agrag-schema-formats-result-ImportResult-warnings) (<code>list\[[FormatWarning](FormatWarning.md)\]</code>) – One entry for each dropped or changed element, in the
  order the importer found them. Empty when the import lost nothing.

## `schema` \{#agrag-schema-formats-result-ImportResult-schema}

```python
schema: GraphSchema
```

## `warnings` \{#agrag-schema-formats-result-ImportResult-warnings}

```python
warnings: list[FormatWarning] = field(default_factory=list)
```
