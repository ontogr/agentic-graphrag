---
title: agrag.common.data_models.document.HeadingRef
sidebar_label: HeadingRef
---

# `agrag.common.data_models.document.HeadingRef` \{#agrag-common-data_models-document-HeadingRef}

Bases: <code>BaseModel</code>

One heading in a document outline.

**Attributes:**

- [**text**](#agrag-common-data_models-document-HeadingRef-text) (<code>str</code>) – The heading text.
- [**level**](#agrag-common-data_models-document-HeadingRef-level) (<code>int</code>) – The heading depth. A top-level heading has level 1.
- [**char_start**](#agrag-common-data_models-document-HeadingRef-char_start) (<code>int</code>) – The start character offset of the heading in the document text. The
  chunker uses this offset to find which heading contains each chunk, since
  the
  base chunker does not detect headings on its own.

## `char_start` \{#agrag-common-data_models-document-HeadingRef-char_start}

```python
char_start: int
```

## `level` \{#agrag-common-data_models-document-HeadingRef-level}

```python
level: int
```

## `text` \{#agrag-common-data_models-document-HeadingRef-text}

```python
text: str
```
