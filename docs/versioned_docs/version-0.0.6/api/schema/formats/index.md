---
title: agrag.schema.formats
sidebar_label: formats
---

# `agrag.schema.formats` \{#agrag-schema-formats}

Import and export schemas in other formats.

**Modules:**

- [**dispatch**](dispatch/index.md) – Hooks that let `load_schema` read Pydantic classes and Turtle files.
- [**errors**](errors/index.md) – Errors raised by schema format importers.
- [**json_schema**](json_schema/index.md) – Export a GraphSchema as a JSON Schema (draft 2020-12) for extraction output.
- [**jsonld**](jsonld/index.md) – Export GraphSchema declarations as a JSON-LD OWL vocabulary.
- [**owl**](owl/index.md) – Import the supported OWL and RDFS Turtle subset.
- [**pydantic_models**](pydantic_models/index.md) – Import a GraphSchema from Pydantic model classes.
- [**result**](result/index.md) – The value that every schema import returns.
- [**shacl**](shacl/index.md) – Export a GraphSchema as SHACL shapes in Turtle syntax.

**Classes:**

- [**FormatWarning**](result/FormatWarning.md) – One thing an import dropped, changed or could not map.
- [**ImportResult**](result/ImportResult.md) – A schema read from another format, with everything the read lost.
- [**SchemaFormatError**](errors/SchemaFormatError.md) – An input document cannot be imported as a supported schema format.
- [**SchemaFormatMissingExtraError**](errors/SchemaFormatMissingExtraError.md) – An optional package required by a schema format is not installed.

**Functions:**

- [**from_pydantic**](pydantic_models/from_pydantic.md) – Read a schema from Pydantic model classes.
- [**load_owl**](owl/load_owl.md) – Load the supported OWL/RDFS subset from a local UTF-8 Turtle file.
- [**loads_owl**](owl/loads_owl.md) – Load the supported OWL/RDFS subset from Turtle text.
- [**to_json_schema**](json_schema/to_json_schema.md) – Export a schema as a JSON Schema that checks a plain extraction document.
- [**to_jsonld**](jsonld/to_jsonld.md) – Return a JSON-LD OWL vocabulary for a graph schema.
- [**to_shacl**](shacl/to_shacl.md) – Export a schema as SHACL shapes in Turtle syntax.
