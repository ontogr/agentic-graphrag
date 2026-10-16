---
title: agrag.common.data_models.extraction.ExtractedRelation
sidebar_label: ExtractedRelation
---

# `agrag.common.data_models.extraction.ExtractedRelation` \{#agrag-common-data_models-extraction-ExtractedRelation}

Bases: <code>BaseModel</code>

One relation mention between two ExtractedEntity mentions in one Chunk.

**Attributes:**

- [**chunk_id**](#agrag-common-data_models-extraction-ExtractedRelation-chunk_id) (<code>UUID</code>) – The id of the Chunk this mention came from.
- [**label**](#agrag-common-data_models-extraction-ExtractedRelation-label) (<code>str</code>) – The RelationType label this mention was extracted as.
- [**source_index**](#agrag-common-data_models-extraction-ExtractedRelation-source_index) (<code>int</code>) – Index of the source entity in the same ExtractionResult.entities.
- [**target_index**](#agrag-common-data_models-extraction-ExtractedRelation-target_index) (<code>int</code>) – Index of the target entity in the same ExtractionResult.entities.
- [**confidence**](#agrag-common-data_models-extraction-ExtractedRelation-confidence) (<code>float | None</code>) – The extractor's confidence in this mention, when available.

## `chunk_id` \{#agrag-common-data_models-extraction-ExtractedRelation-chunk_id}

```python
chunk_id: UUID
```

## `confidence` \{#agrag-common-data_models-extraction-ExtractedRelation-confidence}

```python
confidence: float | None = None
```

## `label` \{#agrag-common-data_models-extraction-ExtractedRelation-label}

```python
label: str
```

## `source_index` \{#agrag-common-data_models-extraction-ExtractedRelation-source_index}

```python
source_index: int
```

## `target_index` \{#agrag-common-data_models-extraction-ExtractedRelation-target_index}

```python
target_index: int
```
