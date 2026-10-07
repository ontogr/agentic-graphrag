---
title: agrag.chunking.NeuralChunker
sidebar_label: NeuralChunker
---

# `agrag.chunking.NeuralChunker` \{#agrag-chunking-NeuralChunker}

Bases: <code>\_ExtraSpanChunker</code>

Cuts where a token classification model predicts a topic break.

Needs the `chunk-neural` extra. The first use downloads the model.

**Attributes:**

- [**model**](#agrag-chunking-NeuralChunker-model) (<code>str | None</code>) – The Hugging Face model id. `None` uses chonkie's default model.
- [**device_map**](#agrag-chunking-NeuralChunker-device_map) (<code>str</code>) – The device for the model, for example `"cpu"` or `"auto"`.
- [**min_characters_per_chunk**](#agrag-chunking-NeuralChunker-min_characters_per_chunk) (<code>int</code>) – The smallest chunk the splitter keeps apart.

**Functions:**

- [**chunk**](#agrag-chunking-NeuralChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-NeuralChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-NeuralChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-NeuralChunker-model_post_init) – Compute the fingerprint only, so the extra is not needed to build.
- [**settings**](#agrag-chunking-NeuralChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-NeuralChunker-spans) – Return the character spans this strategy cuts text into.

## `chunk` \{#agrag-chunking-NeuralChunker-chunk}

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

## `device_map` \{#agrag-chunking-NeuralChunker-device_map}

```python
device_map: str = 'cpu'
```

## `fingerprint` \{#agrag-chunking-NeuralChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `min_characters_per_chunk` \{#agrag-chunking-NeuralChunker-min_characters_per_chunk}

```python
min_characters_per_chunk: int = Field(default=10, gt=0)
```

## `model` \{#agrag-chunking-NeuralChunker-model}

```python
model: str | None = None
```

## `model_config` \{#agrag-chunking-NeuralChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-NeuralChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy would keep the fingerprint and the splitter of the original,
so a copy with changes is built again from its settings.

## `model_post_init` \{#agrag-chunking-NeuralChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Compute the fingerprint only, so the extra is not needed to build.

## `settings` \{#agrag-chunking-NeuralChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `spans` \{#agrag-chunking-NeuralChunker-spans}

```python
spans(text:str) -> list[tuple[int, int]]
```

Return the character spans this strategy cuts text into.

**Raises:**

- <code>[ChunkerMissingExtraError](base/ChunkerMissingExtraError.md)</code> – The package extra is not installed.

## `strategy` \{#agrag-chunking-NeuralChunker-strategy}

```python
strategy: str
```

The strategy name, `"neural"`.
