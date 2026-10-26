---
title: agrag.loaders.common.resolve_text_column
sidebar_label: resolve_text_column
---

# `agrag.loaders.common.resolve_text_column` \{#agrag-loaders-common-resolve_text_column}

```python
resolve_text_column(headers:list[str], text_column:str | None) -> str
```

Pick the column that holds document text.

When the caller passes `text_column`, this function returns it after confirming
the
column exists. When the caller passes nothing, this function returns a common text
column name (`text`, `body`, `content`, or `description`) if present, and
otherwise the last column.

**Parameters:**

- **headers** (<code>list\[str\]</code>) – The column names in the record source.
- **text_column** (<code>str | None</code>) – The column the caller asked for, when given.

**Returns:**

- <code>str</code> – The chosen text column name.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – The caller named a column that the source does not have,
  or the source has no columns at all.
