---
title: agrag.chunking.chunker.ChunkPlacement
sidebar_label: ChunkPlacement
---

# `agrag.chunking.chunker.ChunkPlacement` \{#agrag-chunking-chunker-ChunkPlacement}

```python
ChunkPlacement(chunk_index:int, parent_node_id:UUID, order:int) -> None
```

Where one chunk hangs in the structure of its document.

**Attributes:**

- [**chunk_index**](#agrag-chunking-chunker-ChunkPlacement-chunk_index) (<code>int</code>) – The index of the chunk in `ChunkedDocument.chunks`.
- [**parent_node_id**](#agrag-chunking-chunker-ChunkPlacement-parent_node_id) (<code>UUID</code>) – The id of the table node the chunk came from, or of the
  lowest section that holds its text, or of the document node when no
  section does.
- [**order**](#agrag-chunking-chunker-ChunkPlacement-order) (<code>int</code>) – The edge order under the parent: the reading position of the first
  unit in a text chunk, or the chunk index for a table chunk.

## `chunk_index` \{#agrag-chunking-chunker-ChunkPlacement-chunk_index}

```python
chunk_index: int
```

## `order` \{#agrag-chunking-chunker-ChunkPlacement-order}

```python
order: int
```

## `parent_node_id` \{#agrag-chunking-chunker-ChunkPlacement-parent_node_id}

```python
parent_node_id: UUID
```
