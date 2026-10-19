---
title: agrag.schema.formats.jsonld.to_jsonld
sidebar_label: to_jsonld
---

# `agrag.schema.formats.jsonld.to_jsonld` \{#agrag-schema-formats-jsonld-to_jsonld}

```python
to_jsonld(schema:GraphSchema, *, base_iri:str | None = None) -> dict[str, Any]
```

Return a JSON-LD OWL vocabulary for a graph schema.

Entity types become OWL classes. Entity properties use entity-qualified IRIs
so declarations with the same property name on different types stay distinct.
Relation endpoint sets use OWL union classes, preserving alternative domains
and ranges instead of implying an intersection. Pattern pairs, symmetry,
requiredness, enums and cardinality limits above one use `agrag` annotations.
Empty relation patterns do not create domain or range axioms.

**Parameters:**

- **schema** (<code>[GraphSchema](../../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema to export.
- **base_iri** (<code>str | None</code>) – Replacement namespace, or None for the schema-name namespace.

**Returns:**

- <code>dict\[str, Any\]</code> – A plain JSON-serializable JSON-LD document.
