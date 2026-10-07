---
title: agrag.chunking.base.SpanChunker
sidebar_label: SpanChunker
---

# `agrag.chunking.base.SpanChunker` \{#agrag-chunking-base-SpanChunker}

Bases: <code>[Chunker](Chunker.md)</code>

A chunker that only decides where to cut. Text and offsets come from the source.

Subclasses build an engine that returns objects with `start_index` and
`end_index` for a text. The chunk text is always a slice of the document text,
so a lossy tokenizer round trip cannot change it.

**Functions:**

- [**chunk**](#agrag-chunking-base-SpanChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-base-SpanChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-base-SpanChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-base-SpanChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-base-SpanChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-base-SpanChunker-spans) – Return the half-open character spans this strategy cuts text into.

**Attributes:**

- [**model_config**](#agrag-chunking-base-SpanChunker-model_config) –
- [**strategy**](#agrag-chunking-base-SpanChunker-strategy) (<code>str</code>) – The stable name of this strategy, for example `"recursive"`.

## `chunk` \{#agrag-chunking-base-SpanChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](../../common/data_models/document/Document-ref.md)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code> – The chunks, in document order, each with `chunker` and
  `chunker_hash` set. A strategy that sets `chunker` itself keeps
  its value.

**Raises:**

- <code>[ChunkingError](ChunkingError.md)</code> – The strategy returned chunks that break the contract.

## `fingerprint` \{#agrag-chunking-base-SpanChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-base-SpanChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-base-SpanChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy keeps the fingerprint and the splitter of the original.
A copy with changes is built again from its configuration.

## `model_post_init` \{#agrag-chunking-base-SpanChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

## `settings` \{#agrag-chunking-base-SpanChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `spans` \{#agrag-chunking-base-SpanChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the half-open character spans this strategy cuts text into.

A cut inside a character that a tokenizer splits into several tokens makes
an empty piece. This method drops empty pieces, and no text is lost with them.

**Parameters:**

- **text** (<code>str</code>) – The text to cut.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – The spans, in order, all non-empty.

## `strategy` \{#agrag-chunking-base-SpanChunker-strategy}

```python
strategy: str
```

The stable name of this strategy, for example `"recursive"`.
