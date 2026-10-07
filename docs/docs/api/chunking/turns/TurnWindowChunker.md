---
title: agrag.chunking.turns.TurnWindowChunker
sidebar_label: TurnWindowChunker
---

# `agrag.chunking.turns.TurnWindowChunker` \{#agrag-chunking-turns-TurnWindowChunker}

Bases: <code>[Chunker](../base/Chunker.md)</code>

Packs whole chat turns into windows of at most `chunk_size` tokens.

The chunker reads `Document.turns`. A window holds one or more whole turns, and
a chunk boundary never falls inside a turn. Tokens are counted for each turn
alone, so the separators between turns are not part of the count. Text before
the first turn joins the first window, and text after a turn joins the window
that holds that turn.

A turn above the budget is split by `fallback`, and its chunks have the
chunker name `turn-window:<fallback strategy>`. A document without turns is
split by `fallback` as a whole and its chunks have the same name.

**Attributes:**

- [**chunk_size**](#agrag-chunking-turns-TurnWindowChunker-chunk_size) (<code>int</code>) – The most tokens in a window, counted with `tokenizer`.
- [**turn_overlap**](#agrag-chunking-turns-TurnWindowChunker-turn_overlap) (<code>int</code>) – The number of turns that a window repeats from the window
  before it. A window always moves on by at least one turn.
- [**tokenizer**](#agrag-chunking-turns-TurnWindowChunker-tokenizer) (<code>str</code>) – The tokenizer that counts size. `"character"` counts characters.
- [**fallback**](#agrag-chunking-turns-TurnWindowChunker-fallback) (<code>SerializeAsAny\[[SpanChunker](../base/SpanChunker.md)\]</code>) – The chunker for a turn above the budget and for a document without
  turns.

**Functions:**

- [**chunk**](#agrag-chunking-turns-TurnWindowChunker-chunk) – Split a document into chunks.
- [**fingerprint**](#agrag-chunking-turns-TurnWindowChunker-fingerprint) – Return the hash of `settings()`, 16 hex characters.
- [**model_copy**](#agrag-chunking-turns-TurnWindowChunker-model_copy) – Copy the chunker, validating any changed setting.
- [**model_post_init**](#agrag-chunking-turns-TurnWindowChunker-model_post_init) – Load the tokenizer once, so a bad name fails at construction.
- [**settings**](#agrag-chunking-turns-TurnWindowChunker-settings) – Return the strategy name and every setting as JSON-safe data.

## `chunk` \{#agrag-chunking-turns-TurnWindowChunker-chunk}

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

## `chunk_size` \{#agrag-chunking-turns-TurnWindowChunker-chunk_size}

```python
chunk_size: int = Field(default=256, gt=0)
```

## `fallback` \{#agrag-chunking-turns-TurnWindowChunker-fallback}

```python
fallback: SerializeAsAny[SpanChunker] = Field(default_factory=RecursiveChunker)
```

## `fingerprint` \{#agrag-chunking-turns-TurnWindowChunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of `settings()`, 16 hex characters.

## `model_config` \{#agrag-chunking-turns-TurnWindowChunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_copy` \{#agrag-chunking-turns-TurnWindowChunker-model_copy}

```python
model_copy(*, update:Mapping[str, Any] | None = None, deep:bool = False) -> Self
```

Copy the chunker, validating any changed setting.

A plain copy keeps the fingerprint and the splitter of the original.
A copy with changes is built again from its configuration.

## `model_post_init` \{#agrag-chunking-turns-TurnWindowChunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Load the tokenizer once, so a bad name fails at construction.

## `settings` \{#agrag-chunking-turns-TurnWindowChunker-settings}

```python
settings() -> dict[str, Any]
```

Return the strategy name and every setting as JSON-safe data.

A setting that is itself a chunker appears as that chunker's settings.

## `strategy` \{#agrag-chunking-turns-TurnWindowChunker-strategy}

```python
strategy: str
```

The strategy name, `"turn-window"`.

## `tokenizer` \{#agrag-chunking-turns-TurnWindowChunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```

## `turn_overlap` \{#agrag-chunking-turns-TurnWindowChunker-turn_overlap}

```python
turn_overlap: int = Field(default=0, ge=0)
```
