---
title: agrag.ingestion.stats.chunking.ChunkingMatch
sidebar_label: ChunkingMatch
---

# `agrag.ingestion.stats.chunking.ChunkingMatch` \{#agrag-ingestion-stats-chunking-ChunkingMatch}

Bases: <code>BaseModel</code>

The chunker that one document got, and what it produced.

**Attributes:**

- [**document_key**](#agrag-ingestion-stats-chunking-ChunkingMatch-document_key) (<code>str</code>) – The key of the chunked document.
- [**rule**](#agrag-ingestion-stats-chunking-ChunkingMatch-rule) (<code>int | None</code>) – The index of the matching rule, or `None` for the fallback.
- [**strategy**](#agrag-ingestion-stats-chunking-ChunkingMatch-strategy) (<code>str</code>) – The strategy name of the chunker.
- [**chunker_hash**](#agrag-ingestion-stats-chunking-ChunkingMatch-chunker_hash) (<code>str</code>) – The fingerprint of the chunker settings.
- [**chunks**](#agrag-ingestion-stats-chunking-ChunkingMatch-chunks) (<code>int</code>) – The number of chunks the chunker produced.
- [**chunks_by_chunker**](#agrag-ingestion-stats-chunking-ChunkingMatch-chunks_by_chunker) (<code>dict\[str, int\]</code>) – Chunk counts per chunker name. A strategy that hands a
  part to a fallback names those chunks `<strategy>:<fallback>`, so this
  can hold more than one name. Empty means every chunk has `strategy`.

## `chunker_hash` \{#agrag-ingestion-stats-chunking-ChunkingMatch-chunker_hash}

```python
chunker_hash: str
```

## `chunks` \{#agrag-ingestion-stats-chunking-ChunkingMatch-chunks}

```python
chunks: int
```

## `chunks_by_chunker` \{#agrag-ingestion-stats-chunking-ChunkingMatch-chunks_by_chunker}

```python
chunks_by_chunker: dict[str, int] = Field(default_factory=dict)
```

## `document_key` \{#agrag-ingestion-stats-chunking-ChunkingMatch-document_key}

```python
document_key: str
```

## `rule` \{#agrag-ingestion-stats-chunking-ChunkingMatch-rule}

```python
rule: int | None
```

## `strategy` \{#agrag-ingestion-stats-chunking-ChunkingMatch-strategy}

```python
strategy: str
```
