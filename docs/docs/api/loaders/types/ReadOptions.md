---
title: agrag.loaders.types.ReadOptions
sidebar_label: ReadOptions
---

# `agrag.loaders.types.ReadOptions` \{#agrag-loaders-types-ReadOptions}

```python
ReadOptions(encoding:str | None = None, max_document_bytes:int = 32 * 1024 * 1024, store_text:bool = True, store_raw_record:bool = False, text_column:str | None = None, id_column:str | None = None, title_column:str | None = None, published_at_column:str | None = None, content_date_column:str | None = None, json_mode:JsonMode = JsonMode.AUTO, csv_mode:CsvMode = CsvMode.ROWS, csv_delimiter:str | None = None, normalization:Normalization = Normalization()) -> None
```

Per-source reader configuration.

Frozen so it is safe to share across worker processes.

**Attributes:**

- [**encoding**](#agrag-loaders-types-ReadOptions-encoding) (<code>str | None</code>) – The text encoding to use. `None` lets the decoder detect it.
- [**max_document_bytes**](#agrag-loaders-types-ReadOptions-max_document_bytes) (<code>int</code>) – The largest source, prose or record, the loader will read.
- [**store_text**](#agrag-loaders-types-ReadOptions-store_text) (<code>bool</code>) – When false, the document text is an empty string.
- [**store_raw_record**](#agrag-loaders-types-ReadOptions-store_raw_record) (<code>bool</code>) – When true, a record document keeps its raw row data.
- [**text_column**](#agrag-loaders-types-ReadOptions-text_column) (<code>str | None</code>) – The column that holds document text. `None` uses the first of
  `text`, `body`, `content` and `description` that exists, or the
  last column.
- [**id_column**](#agrag-loaders-types-ReadOptions-id_column) (<code>str | None</code>) – The column whose value becomes the document id.
- [**title_column**](#agrag-loaders-types-ReadOptions-title_column) (<code>str | None</code>) – The column whose value becomes the document title.
- [**published_at_column**](#agrag-loaders-types-ReadOptions-published_at_column) (<code>str | None</code>) – The column whose ISO date or date-time becomes
  `Document.published_at`. Blank values mean no date.
- [**content_date_column**](#agrag-loaders-types-ReadOptions-content_date_column) (<code>str | None</code>) – The column whose ISO date or date-time becomes
  `Document.content_date`. Blank values mean no date.
- [**json_mode**](#agrag-loaders-types-ReadOptions-json_mode) (<code>[JsonMode](JsonMode.md)</code>) – The JSON reading mode.
- [**csv_mode**](#agrag-loaders-types-ReadOptions-csv_mode) (<code>[CsvMode](CsvMode.md)</code>) – The CSV reading mode.
- [**csv_delimiter**](#agrag-loaders-types-ReadOptions-csv_delimiter) (<code>str | None</code>) – The column separator. `None` infers it from the extension.
- [**normalization**](#agrag-loaders-types-ReadOptions-normalization) (<code>[Normalization](../../common/data_models/normalization/Normalization-ref.md)</code>) – How to normalize decoded text: byte-order mark, newline form
  and Unicode form. The default removes the mark, uses LF and applies NFKC.
  Chunk offsets index the normalized text.

## `content_date_column` \{#agrag-loaders-types-ReadOptions-content_date_column}

```python
content_date_column: str | None = None
```

## `csv_delimiter` \{#agrag-loaders-types-ReadOptions-csv_delimiter}

```python
csv_delimiter: str | None = None
```

## `csv_mode` \{#agrag-loaders-types-ReadOptions-csv_mode}

```python
csv_mode: CsvMode = CsvMode.ROWS
```

## `encoding` \{#agrag-loaders-types-ReadOptions-encoding}

```python
encoding: str | None = None
```

## `id_column` \{#agrag-loaders-types-ReadOptions-id_column}

```python
id_column: str | None = None
```

## `json_mode` \{#agrag-loaders-types-ReadOptions-json_mode}

```python
json_mode: JsonMode = JsonMode.AUTO
```

## `max_document_bytes` \{#agrag-loaders-types-ReadOptions-max_document_bytes}

```python
max_document_bytes: int = 32 * 1024 * 1024
```

## `normalization` \{#agrag-loaders-types-ReadOptions-normalization}

```python
normalization: Normalization = field(default_factory=Normalization)
```

## `published_at_column` \{#agrag-loaders-types-ReadOptions-published_at_column}

```python
published_at_column: str | None = None
```

## `store_raw_record` \{#agrag-loaders-types-ReadOptions-store_raw_record}

```python
store_raw_record: bool = False
```

## `store_text` \{#agrag-loaders-types-ReadOptions-store_text}

```python
store_text: bool = True
```

## `text_column` \{#agrag-loaders-types-ReadOptions-text_column}

```python
text_column: str | None = None
```

## `title_column` \{#agrag-loaders-types-ReadOptions-title_column}

```python
title_column: str | None = None
```
