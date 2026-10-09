---
title: agrag.chunking.chunker
sidebar_label: chunker
---

# `agrag.chunking.chunker` \{#agrag-chunking-chunker}

The section chunker: one packer that serves every source format.

**Classes:**

- [**Chunker**](Chunker-ref.md) – Packs the sections of a Document into chunks.
- [**ChunkingError**](ChunkingError.md) – A chunker could not split a document without changing its text.
- [**TextPiece**](TextPiece.md) – A piece of text that `Chunker.split` made.

**Functions:**

- [**fingerprint_of**](fingerprint_of.md) – Return a short stable hash of a JSON-safe value.

**Attributes:**

- [**CHUNKER_NAME**](CHUNKER_NAME.md) –
- [**DEFAULT_SIZE**](DEFAULT_SIZE.md) –
- [**DEFAULT_TOKENIZER**](DEFAULT_TOKENIZER.md) –
