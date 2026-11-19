---
title: agrag.ingestion.extract.UnparsableExtractionError
sidebar_label: UnparsableExtractionError
---

# `agrag.ingestion.extract.UnparsableExtractionError` \{#agrag-ingestion-extract-UnparsableExtractionError}

```python
UnparsableExtractionError(chunk_id:UUID) -> None
```

Bases: <code>[IngestionError](../../loaders/errors/IngestionError.md)</code>

The LLM replied, but the reply holds no JSON answer.

BAML turns a reply it cannot read into an empty result instead of raising.
This error tells that case apart from a model that answered "nothing found".

**Attributes:**

- [**chunk_id**](#agrag-ingestion-extract-UnparsableExtractionError-chunk_id) – The chunk whose extraction failed.

## `chunk_id` \{#agrag-ingestion-extract-UnparsableExtractionError-chunk_id}

```python
chunk_id = chunk_id
```
