---
title: agrag.chunking.chunker.Chunker
sidebar_label: Chunker
---

# `agrag.chunking.chunker.Chunker` \{#agrag-chunking-chunker-Chunker}

```python
Chunker(size:int = DEFAULT_SIZE, min_size:int | None = None, tokenizer:str = DEFAULT_TOKENIZER) -> None
```

Packs the sections of a Document into chunks.

The chunker walks the sections in reading order. It packs the units of a
section into a chunk until the next unit would pass `size` tokens. It splits a
unit that is over `size` on its own, at paragraph, sentence, clause or word
boundaries. When a section ends and the open chunk holds fewer than `min_size`
tokens, the chunk goes on into the next section. A table never mixes with text:
it becomes one chunk, or row groups that each repeat the header row.

A chunk joins the text of its pieces with a blank line. Size counts that joined
text: every piece plus every blank line between pieces. A document whose units
all carry text offsets gives text provenance over the span of its units. A
document whose units carry no offsets gives page provenance.

**Attributes:**

- [**size**](#agrag-chunking-chunker-Chunker-size) (<code>int</code>) – The most tokens in a chunk.
- [**min_size**](#agrag-chunking-chunker-Chunker-min_size) (<code>int | None</code>) – A chunk with fewer tokens than this goes on into the next section.
  `None`, the default, means a quarter of `size`.
- [**tokenizer**](#agrag-chunking-chunker-Chunker-tokenizer) (<code>str</code>) – The tokenizer that counts tokens. A name that chonkie accepts.

**Functions:**

- [**chunk**](#agrag-chunking-chunker-Chunker-chunk) – Split a document into chunks with their placements.
- [**count_tokens**](#agrag-chunking-chunker-Chunker-count_tokens) – Return the number of tokens in a text, counted with `tokenizer`.
- [**settings**](#agrag-chunking-chunker-Chunker-settings) – Return the settings as plain data.
- [**split**](#agrag-chunking-chunker-Chunker-split) – Split a text into pieces of at most `size` tokens.

## `chunk` \{#agrag-chunking-chunker-Chunker-chunk}

```python
chunk(document:Document) -> ChunkedDocument
```

Split a document into chunks with their placements.

**Parameters:**

- **document** (<code>[Document](../../common/data_models/document/Document-ref.md)</code>) – The document to split.

**Returns:**

- <code>[ChunkedDocument](ChunkedDocument.md)</code> – The chunks in reading order with one placement per chunk.

**Raises:**

- <code>[ChunkingError](ChunkingError.md)</code> – The document mixes units that carry text offsets with
  units that carry none, or the splitter changed or dropped text.

## `count_tokens` \{#agrag-chunking-chunker-Chunker-count_tokens}

```python
count_tokens(text:str) -> int
```

Return the number of tokens in a text, counted with `tokenizer`.

## `effective_min_size` \{#agrag-chunking-chunker-Chunker-effective_min_size}

```python
effective_min_size: int
```

Return the merge threshold: `min_size`, or a quarter of `size`.

## `fingerprint` \{#agrag-chunking-chunker-Chunker-fingerprint}

```python
fingerprint: str
```

Return the hash of the settings. Equal settings give equal hashes.

## `min_size` \{#agrag-chunking-chunker-Chunker-min_size}

```python
min_size: int | None = None
```

## `settings` \{#agrag-chunking-chunker-Chunker-settings}

```python
settings() -> dict[str, Any]
```

Return the settings as plain data.

## `size` \{#agrag-chunking-chunker-Chunker-size}

```python
size: int = DEFAULT_SIZE
```

## `split` \{#agrag-chunking-chunker-Chunker-split}

```python
split(text:str) -> list[TextPiece]
```

Split a text into pieces of at most `size` tokens.

**Parameters:**

- **text** (<code>str</code>) – The text to split.

**Returns:**

- <code>list\[[TextPiece](TextPiece.md)\]</code> – The pieces in order. The text of each piece equals the slice of the

**Raises:**

- <code>[ChunkingError](ChunkingError.md)</code> – A piece does not match its slice, or the pieces do not
  join back into the text.

## `tokenizer` \{#agrag-chunking-chunker-Chunker-tokenizer}

```python
tokenizer: str = DEFAULT_TOKENIZER
```
