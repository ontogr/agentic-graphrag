---
title: agrag.ingestion.stats.chunking.ChunkingStats
sidebar_label: ChunkingStats
---

# `agrag.ingestion.stats.chunking.ChunkingStats` \{#agrag-ingestion-stats-chunking-ChunkingStats}

Bases: <code>BaseModel</code>

Chunking-stage results.

**Attributes:**

- [**chunks**](#agrag-ingestion-stats-chunking-ChunkingStats-chunks) (<code>int</code>) – The number of chunks made.
- [**sections**](#agrag-ingestion-stats-chunking-ChunkingStats-sections) (<code>int</code>) – The number of sections in the chunked documents.
- [**tables**](#agrag-ingestion-stats-chunking-ChunkingStats-tables) (<code>int</code>) – The number of tables in the chunked documents.
- [**figures**](#agrag-ingestion-stats-chunking-ChunkingStats-figures) (<code>int</code>) – The number of figures in the chunked documents.

**Functions:**

- [**from_documents**](#agrag-ingestion-stats-chunking-ChunkingStats-from_documents) – Count what the chunker and the loaders produced.

## `chunks` \{#agrag-ingestion-stats-chunking-ChunkingStats-chunks}

```python
chunks: int = 0
```

## `figures` \{#agrag-ingestion-stats-chunking-ChunkingStats-figures}

```python
figures: int = 0
```

## `from_documents` \{#agrag-ingestion-stats-chunking-ChunkingStats-from_documents}

```python
from_documents(documents:Sequence[Document], chunks:Sequence[Chunk]) -> ChunkingStats
```

Count what the chunker and the loaders produced.

**Parameters:**

- **documents** (<code>Sequence\[[Document](../../../common/data_models/document/Document-ref.md)\]</code>) – The documents that were chunked.
- **chunks** (<code>Sequence\[[Chunk](../../../common/data_models/chunk/Chunk-ref.md)\]</code>) – The chunks made from them.

**Returns:**

- <code>ChunkingStats</code> – The counts.

## `sections` \{#agrag-ingestion-stats-chunking-ChunkingStats-sections}

```python
sections: int = 0
```

## `tables` \{#agrag-ingestion-stats-chunking-ChunkingStats-tables}

```python
tables: int = 0
```
