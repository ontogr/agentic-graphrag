---
title: agrag.common.data_models.extraction.ExtractedEntity
sidebar_label: ExtractedEntity
---

# `agrag.common.data_models.extraction.ExtractedEntity` \{#agrag-common-data_models-extraction-ExtractedEntity}

Bases: <code>BaseModel</code>

One entity mention found in a single Chunk.

Not a graph node: this has no id and no canonical identity. Resolution decides
which ExtractedEntity mentions refer to the same real-world thing.

**Attributes:**

- [**chunk_id**](#agrag-common-data_models-extraction-ExtractedEntity-chunk_id) (<code>UUID</code>) – The id of the Chunk this mention came from.
- [**label**](#agrag-common-data_models-extraction-ExtractedEntity-label) (<code>str</code>) – The EntityType label this mention was extracted as.
- [**text**](#agrag-common-data_models-extraction-ExtractedEntity-text) (<code>str</code>) – The mention's surface text.
- [**char_start**](#agrag-common-data_models-extraction-ExtractedEntity-char_start) (<code>int</code>) – The start character offset within the chunk's text.
- [**char_end**](#agrag-common-data_models-extraction-ExtractedEntity-char_end) (<code>int</code>) – The end character offset within the chunk's text.
- [**confidence**](#agrag-common-data_models-extraction-ExtractedEntity-confidence) (<code>float | None</code>) – The extractor's confidence in this mention, when available.
- [**properties**](#agrag-common-data_models-extraction-ExtractedEntity-properties) (<code>dict\[str, object\]</code>) – Schema-declared property values this mention carries,
  keyed by property name. Empty for an extractor that only reports
  spans. normalize_extraction_result drops any key that the schema
  does not declare for this mention's label.

## `char_end` \{#agrag-common-data_models-extraction-ExtractedEntity-char_end}

```python
char_end: int
```

## `char_start` \{#agrag-common-data_models-extraction-ExtractedEntity-char_start}

```python
char_start: int
```

## `chunk_id` \{#agrag-common-data_models-extraction-ExtractedEntity-chunk_id}

```python
chunk_id: UUID
```

## `confidence` \{#agrag-common-data_models-extraction-ExtractedEntity-confidence}

```python
confidence: float | None = None
```

## `label` \{#agrag-common-data_models-extraction-ExtractedEntity-label}

```python
label: str
```

## `properties` \{#agrag-common-data_models-extraction-ExtractedEntity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

## `text` \{#agrag-common-data_models-extraction-ExtractedEntity-text}

```python
text: str
```
