---
title: agrag.common.data_models.extraction.ExtractionResult
sidebar_label: ExtractionResult
---

# `agrag.common.data_models.extraction.ExtractionResult` \{#agrag-common-data_models-extraction-ExtractionResult}

Bases: <code>BaseModel</code>

The entities and relations one Extractor call found in one Chunk.

**Attributes:**

- [**entities**](#agrag-common-data_models-extraction-ExtractionResult-entities) (<code>list\[[ExtractedEntity](ExtractedEntity.md)\]</code>) – The mentions found, in extraction order.
- [**relations**](#agrag-common-data_models-extraction-ExtractionResult-relations) (<code>list\[[ExtractedRelation](ExtractedRelation.md)\]</code>) – The relation mentions found, referencing entities by index.
- [**extractor_name**](#agrag-common-data_models-extraction-ExtractionResult-extractor_name) (<code>str</code>) – Which Extractor produced this result. Set by the
  Extractor itself. Useful for provenance when an EscalatingExtractor
  escalated.

## `entities` \{#agrag-common-data_models-extraction-ExtractionResult-entities}

```python
entities: list[ExtractedEntity]
```

## `extractor_name` \{#agrag-common-data_models-extraction-ExtractionResult-extractor_name}

```python
extractor_name: str
```

## `relations` \{#agrag-common-data_models-extraction-ExtractionResult-relations}

```python
relations: list[ExtractedRelation]
```
