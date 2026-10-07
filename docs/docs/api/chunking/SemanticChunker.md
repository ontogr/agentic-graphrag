---
title: agrag.chunking.SemanticChunker
sidebar_label: SemanticChunker
---

# `agrag.chunking.SemanticChunker` \{#agrag-chunking-SemanticChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts where the meaning of neighbouring sentences changes.

Needs the `chunk-semantic` extra. The chunker embeds sentences with a small
static model and cuts where similarity drops below `threshold`.

**Attributes:**

- [**embedding_model**](#agrag-chunking-SemanticChunker-embedding_model) (<code>str</code>) – The model that embeds sentences. The first use downloads it.
- [**threshold**](#agrag-chunking-SemanticChunker-threshold) (<code>float</code>) – The similarity below which a new chunk starts, from 0 to 1.
- [**chunk_size**](#agrag-chunking-SemanticChunker-chunk_size) (<code>int</code>) – The largest chunk size, as chonkie's semantic chunker counts it.
- [**similarity_window**](#agrag-chunking-SemanticChunker-similarity_window) (<code>int</code>) – The number of sentences that a similarity looks across.

**Functions:**

- [**chunk**](#agrag-chunking-SemanticChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-SemanticChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-SemanticChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-SemanticChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-SemanticChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-SemanticChunker-spans) – Return the character spans this strategy cuts text into.

## `chunk` \{#agrag-chunking-SemanticChunker-chunk}

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

## `chunk_size` \{#agrag-chunking-SemanticChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `embedding_model` \{#agrag-chunking-SemanticChunker-embedding_model}

```python
embedding_model: str = 'minishlab/potion-base-32M'
```

## `fingerprint` \{#agrag-chunking-SemanticChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-SemanticChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-SemanticChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-SemanticChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

## `settings` \{#agrag-chunking-SemanticChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `similarity_window` \{#agrag-chunking-SemanticChunker-similarity_window}

```python
similarity_window: int = Field(default=3, gt=0)
```

## `spans` \{#agrag-chunking-SemanticChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the character spans this strategy cuts text into.

**Raises:**

- <code>[ChunkerMissingExtraError](base/ChunkerMissingExtraError.md)</code> – The package extra is not installed.

## `strategy` \{#agrag-chunking-SemanticChunker-strategy}

```python
strategy: str
```

The strategy name, `"semantic"`.

## `threshold` \{#agrag-chunking-SemanticChunker-threshold}

```python
threshold: float = Field(default=0.8, gt=0, le=1)
```
