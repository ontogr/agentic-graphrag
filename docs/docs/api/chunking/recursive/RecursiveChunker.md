---
title: agrag.chunking.recursive.RecursiveChunker
sidebar_label: RecursiveChunker
---

# `agrag.chunking.recursive.RecursiveChunker` \{#agrag-chunking-recursive-RecursiveChunker}

Bases: <code>[SpanChunker](../base/SpanChunker.md)</code>

Splits on paragraph, sentence and word boundaries, coarsest first.

**Attributes:**

- [**chunk_size**](#agrag-chunking-recursive-RecursiveChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**tokenizer**](#agrag-chunking-recursive-RecursiveChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**min_characters_per_chunk**](#agrag-chunking-recursive-RecursiveChunker-min_characters_per_chunk) (<code>int</code>) – The smallest piece the splitter keeps apart.
- [**levels**](#agrag-chunking-recursive-RecursiveChunker-levels) (<code>tuple\[[SplitLevel](SplitLevel.md), ...\] | None</code>) – The split levels, coarsest first. `None` uses the default levels
  (paragraphs, sentences, punctuation, words, characters).

**Functions:**

- [**chunk**](#agrag-chunking-recursive-RecursiveChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-recursive-RecursiveChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-recursive-RecursiveChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-recursive-RecursiveChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-recursive-RecursiveChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-recursive-RecursiveChunker-spans) – Return the half-open character spans this strategy cuts text into.

## `chunk` \{#agrag-chunking-recursive-RecursiveChunker-chunk}

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

- <code>[ChunkingError](../base/ChunkingError.md)</code> – The strategy returned chunks that break the contract.

## `chunk_size` \{#agrag-chunking-recursive-RecursiveChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `fingerprint` \{#agrag-chunking-recursive-RecursiveChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `levels` \{#agrag-chunking-recursive-RecursiveChunker-levels}

```python
levels: tuple[SplitLevel, ...] | None = None
```

## `min_characters_per_chunk` \{#agrag-chunking-recursive-RecursiveChunker-min_characters_per_chunk}

```python
min_characters_per_chunk: int = Field(default=24, gt=0)
```

## `model_config` \{#agrag-chunking-recursive-RecursiveChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-recursive-RecursiveChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-recursive-RecursiveChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

## `settings` \{#agrag-chunking-recursive-RecursiveChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `spans` \{#agrag-chunking-recursive-RecursiveChunker-spans}

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

## `strategy` \{#agrag-chunking-recursive-RecursiveChunker-strategy}

```python
strategy: str
```

The strategy name, `"recursive"`.

## `tokenizer` \{#agrag-chunking-recursive-RecursiveChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
