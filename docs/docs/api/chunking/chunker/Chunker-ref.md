---
title: agrag.chunking.chunker.Chunker
sidebar_label: Chunker
---

# `agrag.chunking.chunker.Chunker` \{#agrag-chunking-chunker-Chunker}

Bases: <code>BaseModel</code>

Packs the sections of a Document into chunks.

The chunker walks the sections in reading order. It packs the units of a
section into a chunk until the next unit would pass `size` tokens. It splits a
unit that is over `size` on its own, at paragraph, sentence, clause or word
boundaries. When a section ends and the open chunk holds fewer than `min_size`
tokens, the chunk goes on into the next section. A table never mixes with text:
it becomes one chunk, or row groups that each repeat the header row.

A chunk from a text source is an exact slice of `Document.text`. A chunk from a
source with page layout joins the text of its units with a blank line. A document
with no sections, such as one record row, is one unit of text.

Size counts the text of the units. The blank lines that join units are not counted,
so a chunk can pass `size` by a few tokens.

**Attributes:**

- [**size**](#agrag-chunking-chunker-Chunker-size) (<code>int</code>) – The most tokens in a chunk.
- [**min_size**](#agrag-chunking-chunker-Chunker-min_size) (<code>int</code>) – A chunk with fewer tokens than this goes on into the next section.
  Zero, the default, means a quarter of `size`.
- [**tokenizer**](#agrag-chunking-chunker-Chunker-tokenizer) (<code>str</code>) – The tokenizer that counts tokens. A name that chonkie accepts.

**Functions:**

- [**chunk**](#agrag-chunking-chunker-Chunker-chunk) – Split a document into chunks.
- [**count_tokens**](#agrag-chunking-chunker-Chunker-count_tokens) – Return the number of tokens in a text, counted with `tokenizer`.
- [**fingerprint**](#agrag-chunking-chunker-Chunker-fingerprint) – Return the hash of the settings. Equal settings give equal hashes.
- [**model_post_init**](#agrag-chunking-chunker-Chunker-model_post_init) – Check the settings and build the tokenizer and the splitter once.
- [**settings**](#agrag-chunking-chunker-Chunker-settings) – Return the settings as plain data.
- [**split**](#agrag-chunking-chunker-Chunker-split) – Split a text into pieces of at most `size` tokens.

## `chunk` \{#agrag-chunking-chunker-Chunker-chunk}

```python
chunk(document:Document) -> list[Chunk]
```

Split a document into chunks.

**Parameters:**

- **document** (<code>[Document](../../common/data_models/document/Document-ref.md)</code>) – The document to split.

**Returns:**

- <code>list\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code> – The chunks in reading order. Their indexes run from 0 without gaps.

**Raises:**

- <code>[ChunkingError](ChunkingError.md)</code> – The splitter changed or dropped text.

## `count_tokens` \{#agrag-chunking-chunker-Chunker-count_tokens}

```python
count_tokens(text:str) -> int
```

Return the number of tokens in a text, counted with `tokenizer`.

## `fingerprint` \{#agrag-chunking-chunker-Chunker-fingerprint}

```python
fingerprint() -> str
```

Return the hash of the settings. Equal settings give equal hashes.

## `min_size` \{#agrag-chunking-chunker-Chunker-min_size}

```python
min_size: int = Field(default=0, ge=0)
```

## `model_config` \{#agrag-chunking-chunker-Chunker-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `model_post_init` \{#agrag-chunking-chunker-Chunker-model_post_init}

```python
model_post_init(context:Any) -> None
```

Check the settings and build the tokenizer and the splitter once.

## `settings` \{#agrag-chunking-chunker-Chunker-settings}

```python
settings() -> dict[str, Any]
```

Return the settings as plain data.

## `size` \{#agrag-chunking-chunker-Chunker-size}

```python
size: int = Field(default=DEFAULT_SIZE, gt=0)
```

## `split` \{#agrag-chunking-chunker-Chunker-split}

```python
split(text:str) -> list[TextPiece]
```

Split a text into pieces of at most `size` tokens.

**Parameters:**

- **text** (<code>str</code>) – The text to split.

**Returns:**

- <code>list\[[TextPiece](TextPiece.md)\]</code> – The pieces in order. `text` of each piece equals the slice of the text
- <code>list\[[TextPiece](TextPiece.md)\]</code> – from its `start_index` to its `end_index`.

**Raises:**

- <code>[ChunkingError](ChunkingError.md)</code> – A piece does not match its slice, or the pieces do not
  join back into the text.

## `tokenizer` \{#agrag-chunking-chunker-Chunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
