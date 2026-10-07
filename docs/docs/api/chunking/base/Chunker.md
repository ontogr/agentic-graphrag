---
title: agrag.chunking.base.Chunker
sidebar_label: Chunker
---

# `agrag.chunking.base.Chunker` \{#agrag-chunking-base-Chunker}

Bases: <code>BaseModel</code>, <code>ABC</code>

Splits one Document into Chunks and builds their provenance.

A chunker is plain data: its fields are its settings. `settings()` lists them
and `fingerprint()` hashes them, so two chunkers with equal settings have equal
fingerprints. Subclasses implement `strategy` and `_split`. `chunk()`
checks what `_split` returns and records the chunker on every chunk.

**Functions:**

- [**chunk**](#agrag-chunking-base-Chunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-base-Chunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-base-Chunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-base-Chunker-model_post_init) – Compute the fingerprint once, after the settings are validated.
- [**settings**](#agrag-chunking-base-Chunker-settings) – Return the strategy name and every setting as JSON-safe data.

**Attributes:**

- [**model_config**](#agrag-chunking-base-Chunker-model_config) –
- [**strategy**](#agrag-chunking-base-Chunker-strategy) (<code>str</code>) – The stable name of this strategy, for example `"recursive"`.

## `chunk` \{#agrag-chunking-base-Chunker-chunk}

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

## `fingerprint` \{#agrag-chunking-base-Chunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-base-Chunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-base-Chunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy keeps the fingerprint and the splitter of the original.
A copy with changes is built again from its configuration.

## `model_post_init` \{#agrag-chunking-base-Chunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint once, after the settings are validated.

## `settings` \{#agrag-chunking-base-Chunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `strategy` \{#agrag-chunking-base-Chunker-strategy}

```python
strategy: str
```

The stable name of this strategy, for example `"recursive"`.
