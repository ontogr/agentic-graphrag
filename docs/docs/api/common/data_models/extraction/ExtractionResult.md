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
  Extractor itself. Useful for provenance when the pipeline mixes
  extractors.
- [**candidates**](#agrag-common-data_models-extraction-ExtractionResult-candidates) (<code>list\[[CandidateRecord](../candidate/CandidateRecord.md)\]</code>) – Items the extractor found but did not keep, each with the
  reason. Empty when the extractor does not report discards or when
  candidates are turned off.
- [**needs_properties**](#agrag-common-data_models-extraction-ExtractionResult-needs_properties) (<code>bool</code>) – Whether a kept entity has a type that declares
  properties. An extractor that cannot fill property values sets it
  so that a stronger extractor can read the chunk again.

## `candidates` \{#agrag-common-data_models-extraction-ExtractionResult-candidates}

```python
candidates: list[CandidateRecord] = Field(default_factory=list)
```

## `entities` \{#agrag-common-data_models-extraction-ExtractionResult-entities}

```python
entities: list[ExtractedEntity]
```

## `extractor_name` \{#agrag-common-data_models-extraction-ExtractionResult-extractor_name}

```python
extractor_name: str
```

## `needs_properties` \{#agrag-common-data_models-extraction-ExtractionResult-needs_properties}

```python
needs_properties: bool = False
```

## `relations` \{#agrag-common-data_models-extraction-ExtractionResult-relations}

```python
relations: list[ExtractedRelation]
```
