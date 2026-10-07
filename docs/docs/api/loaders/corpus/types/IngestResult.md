---
title: agrag.loaders.corpus.types.IngestResult
sidebar_label: IngestResult
---

# `agrag.loaders.corpus.types.IngestResult` \{#agrag-loaders-corpus-types-IngestResult}

```python
IngestResult(documents:int = 0, sources:int = 0, skipped:int = 0, quarantined:int = 0, quarantined_items:list[tuple[str, str]] = list(), chunks:list[Chunk] = list()) -> None
```

The result of one ingest call.

**Attributes:**

- [**documents**](#agrag-loaders-corpus-types-IngestResult-documents) (<code>int</code>) – The number of documents the call produced.
- [**sources**](#agrag-loaders-corpus-types-IngestResult-sources) (<code>int</code>) – The number of sources the call read.
- [**skipped**](#agrag-loaders-corpus-types-IngestResult-skipped) (<code>int</code>) – The number of sources the call skipped.
- [**quarantined**](#agrag-loaders-corpus-types-IngestResult-quarantined) (<code>int</code>) – The number of sources the call moved to quarantine.
- [**quarantined_items**](#agrag-loaders-corpus-types-IngestResult-quarantined_items) (<code>list\[tuple\[str, str\]\]</code>) – The uri and reason for each quarantined source.
- [**chunks**](#agrag-loaders-corpus-types-IngestResult-chunks) (<code>list\[[Chunk](../../../common/data_models/chunk/Chunk-ref.md)\]</code>) – The chunks the call produced, in document then chunk order.

## `chunks` \{#agrag-loaders-corpus-types-IngestResult-chunks}

```python
chunks: list[Chunk] = field(default_factory=list)
```

## `documents` \{#agrag-loaders-corpus-types-IngestResult-documents}

```python
documents: int = 0
```

## `quarantined` \{#agrag-loaders-corpus-types-IngestResult-quarantined}

```python
quarantined: int = 0
```

## `quarantined_items` \{#agrag-loaders-corpus-types-IngestResult-quarantined_items}

```python
quarantined_items: list[tuple[str, str]] = field(default_factory=list)
```

## `skipped` \{#agrag-loaders-corpus-types-IngestResult-skipped}

```python
skipped: int = 0
```

## `sources` \{#agrag-loaders-corpus-types-IngestResult-sources}

```python
sources: int = 0
```
