---
title: agrag.chunking.token.TokenChunker
sidebar_label: TokenChunker
---

# `agrag.chunking.token.TokenChunker` \{#agrag-chunking-token-TokenChunker}

Bases: <code>[SpanChunker](../base/SpanChunker.md)</code>

Cuts the text into windows of `chunk_size` tokens.

Neighbouring chunks overlap when `chunk_overlap` is set, and each chunk keeps
its exact span in the document.

**Attributes:**

- [**chunk_size**](#agrag-chunking-token-TokenChunker-chunk_size) (<code>int</code>) – The window size, counted with `tokenizer`.
- [**chunk_overlap**](#agrag-chunking-token-TokenChunker-chunk_overlap) (<code>int | float</code>) – The overlap between neighbours. An int counts tokens. A float
  from 0 up to 1 is a share of `chunk_size`.
- [**tokenizer**](#agrag-chunking-token-TokenChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-token-TokenChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-token-TokenChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-token-TokenChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-token-TokenChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-token-TokenChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-token-TokenChunker-spans) – Return the half-open character spans this strategy cuts text into.

## `chunk` \{#agrag-chunking-token-TokenChunker-chunk}

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

## `chunk_overlap` \{#agrag-chunking-token-TokenChunker-chunk_overlap}

```python
chunk_overlap: int | float = Field(default=0, ge=0)
```

## `chunk_size` \{#agrag-chunking-token-TokenChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `fingerprint` \{#agrag-chunking-token-TokenChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-token-TokenChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-token-TokenChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-token-TokenChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

## `settings` \{#agrag-chunking-token-TokenChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `spans` \{#agrag-chunking-token-TokenChunker-spans}

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

## `strategy` \{#agrag-chunking-token-TokenChunker-strategy}

```python
strategy: str
```

The strategy name, `"token"`.

## `tokenizer` \{#agrag-chunking-token-TokenChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
