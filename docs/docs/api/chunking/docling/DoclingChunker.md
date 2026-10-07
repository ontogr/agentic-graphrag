---
title: agrag.chunking.docling.DoclingChunker
sidebar_label: DoclingChunker
---

# `agrag.chunking.docling.DoclingChunker` \{#agrag-chunking-docling-DoclingChunker}

Bases: <code>[Chunker](../base/Chunker.md)</code>

Splits a parsed docling document with docling's hybrid chunker.

The chunker reads the parsed document that the docling loader keeps in
`Document.metadata["_docling_document"]`. Each chunk has page provenance and
the headings above it in `heading_path`. The chunk text is the body without
headings, but headings count against the token budget. Chunk ids include the
fingerprint, so a re-chunk with new settings does not overwrite the old chunks.

**Attributes:**

- [**tokenizer**](#agrag-chunking-docling-DoclingChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. A name with a slash is a Hugging
  Face model id, which needs the network the first time.
- [**max_tokens**](#agrag-chunking-docling-DoclingChunker-max_tokens) (<code>int</code>) – The most tokens in a chunk, headings included.
- [**merge_peers**](#agrag-chunking-docling-DoclingChunker-merge_peers) (<code>bool</code>) – Whether to merge small neighbours under the same headings.
- [**repeat_table_header**](#agrag-chunking-docling-DoclingChunker-repeat_table_header) (<code>bool</code>) – Whether each chunk of a split table repeats its header.
- [**omit_header_on_overflow**](#agrag-chunking-docling-DoclingChunker-omit_header_on_overflow) (<code>bool</code>) – Whether to drop headings from a chunk when they
  would not fit the budget.
- [**table_format**](#agrag-chunking-docling-DoclingChunker-table_format) (<code>Literal['triplet', 'markdown']</code>) – `"triplet"` writes `row, column = value` text and
  `"markdown"` writes a pipe table.

**Functions:**

- [**chunk**](#agrag-chunking-docling-DoclingChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-docling-DoclingChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-docling-DoclingChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-docling-DoclingChunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-docling-DoclingChunker-settings) – Return the strategy name and every setting as JSON-safe data.

## `chunk` \{#agrag-chunking-docling-DoclingChunker-chunk}

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

## `fingerprint` \{#agrag-chunking-docling-DoclingChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `max_tokens` \{#agrag-chunking-docling-DoclingChunker-max_tokens}

```python
max_tokens: int = Field(default=1024, gt=0)
```

## `merge_peers` \{#agrag-chunking-docling-DoclingChunker-merge_peers}

```python
merge_peers: bool = True
```

## `model_config` \{#agrag-chunking-docling-DoclingChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-docling-DoclingChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-docling-DoclingChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

## `omit_header_on_overflow` \{#agrag-chunking-docling-DoclingChunker-omit_header_on_overflow}

```python
omit_header_on_overflow: bool = False
```

## `repeat_table_header` \{#agrag-chunking-docling-DoclingChunker-repeat_table_header}

```python
repeat_table_header: bool = True
```

## `settings` \{#agrag-chunking-docling-DoclingChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `strategy` \{#agrag-chunking-docling-DoclingChunker-strategy}

```python
strategy: str
```

The strategy name, `"docling"`.

## `table_format` \{#agrag-chunking-docling-DoclingChunker-table_format}

```python
table_format: Literal['triplet', 'markdown'] = 'triplet'
```

## `tokenizer` \{#agrag-chunking-docling-DoclingChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
