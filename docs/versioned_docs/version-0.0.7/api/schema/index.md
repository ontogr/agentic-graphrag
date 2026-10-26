---
title: agrag.schema
sidebar_position: 16
---


# `agrag.schema` \{#agrag-schema}

Load and dump schemas in a notation that is short to write.

**Modules:**

- [**canonical**](canonical/index.md) – The canonical dict form of a GraphSchema.
- [**errors**](errors/index.md) – Errors that the schema loader raises.
- [**formats**](formats/index.md) – Import and export schemas in other formats.
- [**loader**](loader/index.md) – Load a GraphSchema from a dict, a label list, JSON, YAML, a path or a preset.
- [**shorthand**](shorthand/index.md) – Readers that turn every accepted notation into canonical dicts.

**Classes:**

- [**SchemaError**](errors/SchemaError.md) – The base class for every schema-loader error.
- [**SchemaIssue**](errors/SchemaIssue.md) – One problem found in a schema source.
- [**SchemaLoadError**](errors/SchemaLoadError.md) – A schema source is invalid.

**Functions:**

- [**dump_schema**](canonical/dump_schema.md) – Return the canonical dict form of a schema.
- [**load_schema**](loader/load_schema.md) – Load a schema from any accepted source.
