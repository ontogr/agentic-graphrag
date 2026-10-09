---
title: agrag.common.data_models.document.Unit
sidebar_label: Unit
---

# `agrag.common.data_models.document.Unit` \{#agrag-common-data_models-document-Unit}

Bases: <code>BaseModel</code>

One piece of content in a section, such as a paragraph or a table.

**Attributes:**

- [**kind**](#agrag-common-data_models-document-Unit-kind) (<code>[UnitKind](UnitKind.md)</code>) – The kind of content.
- [**text**](#agrag-common-data_models-document-Unit-text) (<code>str</code>) – The text of the unit. For a table or figure, the caption, or an empty
  string when it has none.
- [**char_start**](#agrag-common-data_models-document-Unit-char_start) (<code>int | None</code>) – The start character offset of the unit in the document text. A
  text source sets this field. A source that has no text offsets leaves it
  empty.
- [**char_end**](#agrag-common-data_models-document-Unit-char_end) (<code>int | None</code>) – The end character offset of the unit, exclusive. Set together with
  `char_start`.
- [**pages**](#agrag-common-data_models-document-Unit-pages) (<code>list\[[PageSpan](../provenance/PageSpan.md)\]</code>) – The pages and boxes the unit covers. A source with page layout sets
  this field.
- [**caption**](#agrag-common-data_models-document-Unit-caption) (<code>str | None</code>) – The caption of a table or figure.
- [**rows**](#agrag-common-data_models-document-Unit-rows) (<code>list\[list\[str\]\]</code>) – The cell text of a table, row by row. A spanned cell repeats its text
  in every slot it covers. Empty for other kinds.
- [**header_rows**](#agrag-common-data_models-document-Unit-header_rows) (<code>int</code>) – The number of leading rows of a table that are headers. Zero
  when the source does not mark them; see `header_row_count`.

## `caption` \{#agrag-common-data_models-document-Unit-caption}

```python
caption: str | None = None
```

## `char_end` \{#agrag-common-data_models-document-Unit-char_end}

```python
char_end: int | None = None
```

## `char_start` \{#agrag-common-data_models-document-Unit-char_start}

```python
char_start: int | None = None
```

## `header` \{#agrag-common-data_models-document-Unit-header}

```python
header: list[str]
```

Return the column names of a table, one for each column.

The first `header_row_count` rows make the header. Empty when the
table has no rows. A spanned header cell repeats its text in every
slot it covers, so each column keeps each text once.

## `header_row_count` \{#agrag-common-data_models-document-Unit-header_row_count}

```python
header_row_count: int
```

Return how many leading rows of a table form its header.

A Markdown table needs a header line, so the first row is the header
when the source marks none.

## `header_rows` \{#agrag-common-data_models-document-Unit-header_rows}

```python
header_rows: int = Field(default=0, ge=0)
```

## `kind` \{#agrag-common-data_models-document-Unit-kind}

```python
kind: UnitKind
```

## `pages` \{#agrag-common-data_models-document-Unit-pages}

```python
pages: list[PageSpan] = Field(default_factory=list)
```

## `rows` \{#agrag-common-data_models-document-Unit-rows}

```python
rows: list[list[str]] = Field(default_factory=list)
```

## `text` \{#agrag-common-data_models-document-Unit-text}

```python
text: str
```
