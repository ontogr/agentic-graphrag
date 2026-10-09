---
title: agrag.chunking
sidebar_position: 3
---


# `agrag.chunking` \{#agrag-chunking}

Chunking: how a Document becomes Chunks.

`Chunker` packs the sections of a document into chunks. `ChunkedDocument`
carries the chunks with where each chunk hangs. `Graph` takes one.

**Modules:**

- [**chunker**](chunker/index.md) – The section chunker: one packer that serves every source format.

**Classes:**

- [**ChunkPlacement**](chunker/ChunkPlacement.md) – Where one chunk hangs in the structure of its document.
- [**ChunkedDocument**](chunker/ChunkedDocument.md) – The chunks of one document with where each chunk hangs.
- [**Chunker**](chunker/Chunker-ref.md) – Packs the sections of a Document into chunks.
- [**ChunkingError**](chunker/ChunkingError.md) – A chunker could not split a document without changing its text.

**Attributes:**

- [**DEFAULT_TOKENIZER**](chunker/DEFAULT_TOKENIZER.md) –
