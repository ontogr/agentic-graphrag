---
title: agrag.chunking.heading.HeadingChunker
sidebar_label: HeadingChunker
---

# `agrag.chunking.heading.HeadingChunker` \{#agrag-chunking-heading-HeadingChunker}

Bases: <code>[Chunker](../base/Chunker.md)</code>

Cuts a document into sections at its headings and packs them to a budget.

The chunker reads `Document.heading_outline`. A heading of `split_level` or
higher (a level number at or below `split_level`) starts a new section, and no
chunk holds such a heading except at its start. A section within `chunk_size`
tokens is one chunk. A larger section is cut at its deeper headings and the
parts are packed to the budget. A part that is still too large goes to
`fallback`, and its chunks have the chunker name `heading:<fallback strategy>`. A document with no headings goes to `fallback` as a whole and its
chunks have the same name. Only the plain text loaders for Markdown and AsciiDoc
fill the outline.

**Attributes:**

- [**chunk_size**](#agrag-chunking-heading-HeadingChunker-chunk_size) (<code>int</code>) – The most tokens in a chunk, counted with `tokenizer`. Tokens
  are counted for each part alone, so a packed chunk can be a few tokens
  over.
- [**split_level**](#agrag-chunking-heading-HeadingChunker-split_level) (<code>int</code>) – The deepest heading level that starts a new section, from 1 to 6.
- [**tokenizer**](#agrag-chunking-heading-HeadingChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**fallback**](#agrag-chunking-heading-HeadingChunker-fallback) (<code>SerializeAsAny\[[SpanChunker](../base/SpanChunker.md)\]</code>) – The chunker for a part above the budget and for a document without
  headings.

**Functions:**

- [**chunk**](#agrag-chunking-heading-HeadingChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-heading-HeadingChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-heading-HeadingChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-heading-HeadingChunker-model_post_init) – Load the tokenizer once, so a bad name fails at construction.
- [**settings**](#agrag-chunking-heading-HeadingChunker-settings) – Return the strategy name and every setting as JSON-safe data.

## `chunk` \{#agrag-chunking-heading-HeadingChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](../../common/data_models/document/Document-ref.md)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](../base/ChunkingError.md)</code> – The strategy returned chunks that break the contract.

## `chunk_size` \{#agrag-chunking-heading-HeadingChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `fallback` \{#agrag-chunking-heading-HeadingChunker-fallback}

```python
fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)
```

## `fingerprint` \{#agrag-chunking-heading-HeadingChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-heading-HeadingChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-heading-HeadingChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-heading-HeadingChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Load the tokenizer once, so a bad name fails at construction.

## `settings` \{#agrag-chunking-heading-HeadingChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `split_level` \{#agrag-chunking-heading-HeadingChunker-split_level}

```python
split_level: int = Field(default=2, ge=1, le=6)
```

## `strategy` \{#agrag-chunking-heading-HeadingChunker-strategy}

```python
strategy: str
```

The strategy name, `"heading"`.

## `tokenizer` \{#agrag-chunking-heading-HeadingChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
