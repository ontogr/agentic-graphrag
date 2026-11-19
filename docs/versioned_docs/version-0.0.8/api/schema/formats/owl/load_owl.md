---
title: agrag.schema.formats.owl.load_owl
sidebar_label: load_owl
---

# `agrag.schema.formats.owl.load_owl` \{#agrag-schema-formats-owl-load_owl}

```python
load_owl(source:str | Path, *, name:str | None = None, version:str | None = None) -> ImportResult
```

Load the supported OWL/RDFS subset from a local UTF-8 Turtle file.

The name defaults to the file stem and version to `1`. Import warnings
are returned, not logged. Remote paths and ontology imports are not fetched.

**Raises:**

- <code>[SchemaFormatError](../errors/SchemaFormatError.md)</code> – The file or Turtle document cannot be read.
- <code>[SchemaFormatMissingExtraError](../errors/SchemaFormatMissingExtraError.md)</code> – Install the `schema-formats` extra.
- <code>[SchemaLoadError](../../errors/SchemaLoadError.md)</code> – The mapped data fails schema validation.
