---
title: agrag.loaders.types.DecodedText
sidebar_label: DecodedText
---

# `agrag.loaders.types.DecodedText` \{#agrag-loaders-types-DecodedText}

```python
DecodedText(text:str, encoding:str, had_bom:bool, content_hash:str, char_count:int, line_count:int) -> None
```

Output of the four-step decode pipeline.

**Attributes:**

- [**text**](#agrag-loaders-types-DecodedText-text) (<code>str</code>) – The decoded text, normalized as `ReadOptions.normalization` says.
- [**encoding**](#agrag-loaders-types-DecodedText-encoding) (<code>str</code>) – The encoding used to decode the bytes.
- [**had_bom**](#agrag-loaders-types-DecodedText-had_bom) (<code>bool</code>) – Whether the source started with a byte-order mark.
- [**content_hash**](#agrag-loaders-types-DecodedText-content_hash) (<code>str</code>) – The sha256 hash of the normalized text.
- [**char_count**](#agrag-loaders-types-DecodedText-char_count) (<code>int</code>) – The number of characters in `text`.
- [**line_count**](#agrag-loaders-types-DecodedText-line_count) (<code>int</code>) – The number of lines in `text`.

## `char_count` \{#agrag-loaders-types-DecodedText-char_count}

```python
char_count: int
```

## `content_hash` \{#agrag-loaders-types-DecodedText-content_hash}

```python
content_hash: str
```

## `encoding` \{#agrag-loaders-types-DecodedText-encoding}

```python
encoding: str
```

## `had_bom` \{#agrag-loaders-types-DecodedText-had_bom}

```python
had_bom: bool
```

## `line_count` \{#agrag-loaders-types-DecodedText-line_count}

```python
line_count: int
```

## `text` \{#agrag-loaders-types-DecodedText-text}

```python
text: str
```
