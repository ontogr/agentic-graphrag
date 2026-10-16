---
title: agrag.chunking.chunker.TextPiece
sidebar_label: TextPiece
---

# `agrag.chunking.chunker.TextPiece` \{#agrag-chunking-chunker-TextPiece}

```python
TextPiece(text:str, start_index:int, end_index:int, token_count:int) -> None
```

A piece of text that `Chunker.split` made.

**Attributes:**

- [**text**](#agrag-chunking-chunker-TextPiece-text) (<code>str</code>) – The text of the piece. It equals the slice of the source text from
  `start_index` to `end_index`.
- [**start_index**](#agrag-chunking-chunker-TextPiece-start_index) (<code>int</code>) – The offset of the first character in the source text.
- [**end_index**](#agrag-chunking-chunker-TextPiece-end_index) (<code>int</code>) – The offset just past the last character in the source text.
- [**token_count**](#agrag-chunking-chunker-TextPiece-token_count) (<code>int</code>) – The number of tokens in the piece.

## `end_index` \{#agrag-chunking-chunker-TextPiece-end_index}

```python
end_index: int
```

## `start_index` \{#agrag-chunking-chunker-TextPiece-start_index}

```python
start_index: int
```

## `text` \{#agrag-chunking-chunker-TextPiece-text}

```python
text: str
```

## `token_count` \{#agrag-chunking-chunker-TextPiece-token_count}

```python
token_count: int
```
