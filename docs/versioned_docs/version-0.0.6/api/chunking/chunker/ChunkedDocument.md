---
title: agrag.chunking.chunker.ChunkedDocument
sidebar_label: ChunkedDocument
---

# `agrag.chunking.chunker.ChunkedDocument` \{#agrag-chunking-chunker-ChunkedDocument}

```python
ChunkedDocument(chunks:list[Chunk], placements:list[ChunkPlacement]) -> None
```

The chunks of one document with where each chunk hangs.

**Attributes:**

- [**chunks**](#agrag-chunking-chunker-ChunkedDocument-chunks) (<code>list\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code>) – The chunks in reading order. Their indexes run from 0.
- [**placements**](#agrag-chunking-chunker-ChunkedDocument-placements) (<code>list\[[ChunkPlacement](ChunkPlacement.md)\]</code>) – One placement per chunk, in the same order as `chunks`.

## `chunks` \{#agrag-chunking-chunker-ChunkedDocument-chunks}

```python
chunks: list[Chunk]
```

## `placements` \{#agrag-chunking-chunker-ChunkedDocument-placements}

```python
placements: list[ChunkPlacement]
```
