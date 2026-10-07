---
title: agrag.common.data_models.TextProvenance
sidebar_label: TextProvenance
---

# `agrag.common.data_models.TextProvenance` \{#agrag-common-data_models-TextProvenance}

Bases: <code>BaseModel</code>

The location of a chunk inside flattened document text.

The offsets index the normalized text in `Document.text`, not the raw source.
See `Normalization`.

**Attributes:**

- [**kind**](#agrag-common-data_models-TextProvenance-kind) (<code>Literal['text']</code>) – The literal tag `"text"`. Marks this as text provenance.
- [**char_start**](#agrag-common-data_models-TextProvenance-char_start) (<code>int</code>) – The start character offset in the document text.
- [**char_end**](#agrag-common-data_models-TextProvenance-char_end) (<code>int</code>) – The end character offset in the document text.
- [**line_start**](#agrag-common-data_models-TextProvenance-line_start) (<code>int | None</code>) – The start line number. Empty when the loader does not track lines.
- [**line_end**](#agrag-common-data_models-TextProvenance-line_end) (<code>int | None</code>) – The end line number. Empty when the loader does not track lines.

## `char_end` \{#agrag-common-data_models-TextProvenance-char_end}

```python
char_end: int
```

## `char_start` \{#agrag-common-data_models-TextProvenance-char_start}

```python
char_start: int
```

## `kind` \{#agrag-common-data_models-TextProvenance-kind}

```python
kind: Literal['text'] = 'text'
```

## `line_end` \{#agrag-common-data_models-TextProvenance-line_end}

```python
line_end: int | None = None
```

## `line_start` \{#agrag-common-data_models-TextProvenance-line_start}

```python
line_start: int | None = None
```
