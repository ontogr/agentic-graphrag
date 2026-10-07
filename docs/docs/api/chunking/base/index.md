---
title: agrag.chunking.base
sidebar_label: base
---

# `agrag.chunking.base` \{#agrag-chunking-base}

The Chunker contract: how a Document becomes Chunks, and how that is recorded.

**Classes:**

- [**Chunker**](Chunker.md) – Splits one Document into Chunks and builds their provenance.
- [**ChunkerMissingExtraError**](ChunkerMissingExtraError.md) – A chunker needs a package extra that is not installed.
- [**ChunkingError**](ChunkingError.md) – A chunker broke the chunk contract or could not chunk a document.
- [**SpanChunker**](SpanChunker.md) – A chunker that only decides where to cut; text and offsets come from the source.

**Functions:**

- [**fingerprint_of**](fingerprint_of.md) – Return a short stable hash of a JSON-safe value.

**Attributes:**

- [**DEFAULT_TOKENIZER**](DEFAULT_TOKENIZER.md) –
