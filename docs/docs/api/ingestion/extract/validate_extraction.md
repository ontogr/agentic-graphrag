---
title: agrag.ingestion.extract.validate_extraction
sidebar_label: validate_extraction
---

# `agrag.ingestion.extract.validate_extraction` \{#agrag-ingestion-extract-validate_extraction}

```python
validate_extraction(result:ExtractionResult, schema:GraphSchema) -> ExtractionResult
```

Drop entities and relations that the schema does not declare.

The pipeline applies this to the result of every extractor, so a custom
extractor cannot send an undeclared label to the graph. An entity
survives only when its label is a declared EntityType, and keeps only the
property keys that EntityType declares. A relation survives only when both
of its entities survive and `schema.allows` accepts its label and
resolved (source label, target label) pair. Relation indices are remapped
to the surviving entities. A drop is logged with a count.

**Parameters:**

- **result** (<code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code>) – The extractor's result, before schema validation.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema entities and relations are validated against.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – A copy of `result` holding only schema-declared entities and
- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – relations, with relation indices remapped and each entity's properties
- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – limited to its declared keys. `candidates` and `needs_properties`
- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – are unchanged.
