---
title: agrag.chunking.CodeChunker
sidebar_label: CodeChunker
---

# `agrag.chunking.CodeChunker` \{#agrag-chunking-CodeChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts source code along its syntax tree.

Needs the `chunk-code` extra. The parser reports byte offsets, and this
chunker converts them to character offsets, so chunk text equals the source
slice for non-ASCII code too.

**Attributes:**

- [**language**](#agrag-chunking-CodeChunker-language) (<code>str</code>) – A tree-sitter language name, or `"auto"` to detect it.
- [**chunk_size**](#agrag-chunking-CodeChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**tokenizer**](#agrag-chunking-CodeChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-CodeChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-CodeChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-CodeChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-CodeChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-CodeChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-CodeChunker-spans) – Return character spans, converted from the parser's byte spans.

## `chunk` \{#agrag-chunking-CodeChunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

Every chunk has non-empty text, indexes run from 0 without gaps, and a chunk
with text provenance has text equal to `document.text` at its offsets.

**Parameters:**

- **document** (<code>[Document](../common/data_models/document/Document-ref.md)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](../common/data_models/chunk/Chunk-ref.md)\]</code> – The chunks, in document order, each with `chunker` and `chunker_hash`
- <code>list\[[Chunk](../common/data_models/chunk/Chunk-ref.md)\]</code> – set. A strategy that sets `chunker` itself keeps its value.

**Raises:**

- <code>[ChunkingError](base/ChunkingError.md)</code> – The strategy returned chunks that break the contract.

## `chunk_size` \{#agrag-chunking-CodeChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `fingerprint` \{#agrag-chunking-CodeChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `language` \{#agrag-chunking-CodeChunker-language}

```python
language: str = 'auto'
```

## `model_config` \{#agrag-chunking-CodeChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-CodeChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-CodeChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

## `settings` \{#agrag-chunking-CodeChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `spans` \{#agrag-chunking-CodeChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return character spans, converted from the parser's byte spans.

## `strategy` \{#agrag-chunking-CodeChunker-strategy}

```python
strategy: str
```

The strategy name, `"code"`.

## `tokenizer` \{#agrag-chunking-CodeChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
