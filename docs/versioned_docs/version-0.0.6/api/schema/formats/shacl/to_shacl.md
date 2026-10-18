---
title: agrag.schema.formats.shacl.to_shacl
sidebar_label: to_shacl
---

# `agrag.schema.formats.shacl.to_shacl` \{#agrag-schema-formats-shacl-to_shacl}

```python
to_shacl(schema:GraphSchema, *, base_iri:str | None = None) -> str
```

Export a schema as SHACL shapes in Turtle syntax.

Each entity type becomes a `sh:NodeShape` with a
`sh:targetClass`, its description as `rdfs:comment` and each
parent as `rdfs:subClassOf`. Each declared property becomes an
inline `sh:property` shape with `sh:path`, `sh:datatype`,
`sh:minCount` and, for enums, `sh:in`. Each relation type
becomes an `rdf:Property` with its description as
`rdfs:comment`, annotated with its declared patterns and limits,
plus one `sh:property` shape on each endpoint's node shape
naming the allowed classes (`sh:inversePath` on the target side).
Endpoint shapes cover every pair `GraphSchema.allows` accepts,
so descendants and symmetric reversals are included. Cardinality
limits appear both as `sh:maxCount` shapes, which validators
enforce, and as `x-agrag:` annotations for pipelines; patterns
and symmetry appear only as annotations that validators ignore.

**Parameters:**

- **schema** (<code>[GraphSchema](../../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema to export.
- **base_iri** (<code>str | None</code>) – A namespace IRI for the `ex:` prefix. Defaults to
  the schema namespace shared with the JSON-LD export.

**Returns:**

- <code>str</code> – Turtle text describing the schema, written without dependencies.

**Raises:**

- <code>ValueError</code> – If a property name collides with a relation label,
  or the base IRI would break the Turtle output.
