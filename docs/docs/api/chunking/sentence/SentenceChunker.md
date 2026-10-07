---
title: agrag.chunking.sentence.SentenceChunker
sidebar_label: SentenceChunker
---

# `agrag.chunking.sentence.SentenceChunker` \{#agrag-chunking-sentence-SentenceChunker}

Bases: <code>[SpanChunker](../base/SpanChunker.md)</code>

Packs whole sentences into chunks of at most `chunk_size` tokens.

A single sentence longer than `chunk_size` stays whole, so a chunk can be
larger than the budget when the text has a very long sentence.

**Attributes:**

- [**chunk_size**](#agrag-chunking-sentence-SentenceChunker-chunk_size) (<code>int</code>) – The largest chunk size, counted with `tokenizer`.
- [**chunk_overlap**](#agrag-chunking-sentence-SentenceChunker-chunk_overlap) (<code>int</code>) – The overlap between neighbours, in tokens. Each chunk keeps
  its exact span in the document.
- [**min_sentences_per_chunk**](#agrag-chunking-sentence-SentenceChunker-min_sentences_per_chunk) (<code>int</code>) – The fewest sentences in a chunk.
- [**min_characters_per_sentence**](#agrag-chunking-sentence-SentenceChunker-min_characters_per_sentence) (<code>int</code>) – The shortest text that counts as a sentence.
- [**tokenizer**](#agrag-chunking-sentence-SentenceChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.

**Functions:**

- [**chunk**](#agrag-chunking-sentence-SentenceChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-sentence-SentenceChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-sentence-SentenceChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-sentence-SentenceChunker-model_post_init) – Build the engine once, so a bad setting fails at construction.
- [**settings**](#agrag-chunking-sentence-SentenceChunker-settings) – Return the strategy name and every setting as JSON-safe data.
- [**spans**](#agrag-chunking-sentence-SentenceChunker-spans) – Return the half-open character spans this strategy cuts text into.

## `chunk` \{#agrag-chunking-sentence-SentenceChunker-chunk}

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

## `chunk_overlap` \{#agrag-chunking-sentence-SentenceChunker-chunk_overlap}

```python
chunk_overlap: int = Field(default=0, ge=0)
```

## `chunk_size` \{#agrag-chunking-sentence-SentenceChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `fingerprint` \{#agrag-chunking-sentence-SentenceChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `min_characters_per_sentence` \{#agrag-chunking-sentence-SentenceChunker-min_characters_per_sentence}

```python
min_characters_per_sentence: int = Field(default=12, gt=0)
```

## `min_sentences_per_chunk` \{#agrag-chunking-sentence-SentenceChunker-min_sentences_per_chunk}

```python
min_sentences_per_chunk: int = Field(default=1, gt=0)
```

## `model_config` \{#agrag-chunking-sentence-SentenceChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-sentence-SentenceChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy keeps the fingerprint and the splitter of the original.
A copy with changes is built again from its configuration.

## `model_post_init` \{#agrag-chunking-sentence-SentenceChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Build the engine once, so a bad setting fails at construction.

## `settings` \{#agrag-chunking-sentence-SentenceChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `spans` \{#agrag-chunking-sentence-SentenceChunker-spans}

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

## `strategy` \{#agrag-chunking-sentence-SentenceChunker-strategy}

```python
strategy: str
```

The strategy name, `"sentence"`.

## `tokenizer` \{#agrag-chunking-sentence-SentenceChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
