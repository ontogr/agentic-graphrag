---
title: agrag.schema.formats.owl.loads_owl
sidebar_label: loads_owl
---

# `agrag.schema.formats.owl.loads_owl` \{#agrag-schema-formats-owl-loads_owl}

```python
loads_owl(text:str, *, name:str | None = None, version:str | None = None) -> ImportResult
```

Load the supported OWL/RDFS subset from Turtle text.

Only declared types are imported. No reasoning or remote imports run.
Unsupported constructs and lossy mappings appear in the warnings list.
Name and version default to `custom` and `1`.

**Raises:**

- <code>[SchemaFormatError](../errors/SchemaFormatError.md)</code> – Turtle or term identifiers cannot be read.
- <code>[SchemaFormatMissingExtraError](../errors/SchemaFormatMissingExtraError.md)</code> – Install the `schema-formats` extra.
- <code>[SchemaLoadError](../../errors/SchemaLoadError.md)</code> – The mapped data fails schema validation.
