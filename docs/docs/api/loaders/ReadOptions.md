---
title: agrag.loaders.ReadOptions
sidebar_label: ReadOptions
---

# `agrag.loaders.ReadOptions` \{#agrag-loaders-ReadOptions}

```python
ReadOptions(encoding:str | None = None, max_document_bytes:int = 32 * 1024 * 1024, store_text:bool = True, store_raw_record:bool = False, on_error:ErrorPolicy = ErrorPolicy.RAISE, text_column:str | None = None, id_column:str | None = None, title_column:str | None = None, json_mode:JsonMode = JsonMode.AUTO, csv_mode:CsvMode = CsvMode.ROWS, csv_delimiter:str | None = None, html_selector:str | None = None, normalization:Normalization = Normalization()) -> None
```

Per-source reader configuration.

Frozen so it is safe to share across worker processes.

**Attributes:**

- [**encoding**](#agrag-loaders-ReadOptions-encoding) (<code>str | None</code>) – The text encoding to use. `None` lets the decoder detect it.
- [**max_document_bytes**](#agrag-loaders-ReadOptions-max_document_bytes) (<code>int</code>) – The largest prose source the loader will read.
- [**store_text**](#agrag-loaders-ReadOptions-store_text) (<code>bool</code>) – When false, the document text is an empty string.
- [**store_raw_record**](#agrag-loaders-ReadOptions-store_raw_record) (<code>bool</code>) – When true, a record document keeps its raw row data.
- [**on_error**](#agrag-loaders-ReadOptions-on_error) (<code>[ErrorPolicy](corpus/types/ErrorPolicy.md)</code>) – The error policy to apply inside the reader.
- [**text_column**](#agrag-loaders-ReadOptions-text_column) (<code>str | None</code>) – The column that holds document text. Required for record sources.
- [**id_column**](#agrag-loaders-ReadOptions-id_column) (<code>str | None</code>) – The column whose value becomes the document id.
- [**title_column**](#agrag-loaders-ReadOptions-title_column) (<code>str | None</code>) – The column whose value becomes the document title.
- [**json_mode**](#agrag-loaders-ReadOptions-json_mode) (<code>[JsonMode](corpus/types/JsonMode.md)</code>) – The JSON reading mode.
- [**csv_mode**](#agrag-loaders-ReadOptions-csv_mode) (<code>[CsvMode](corpus/types/CsvMode.md)</code>) – The CSV reading mode.
- [**csv_delimiter**](#agrag-loaders-ReadOptions-csv_delimiter) (<code>str | None</code>) – The column separator. `None` infers it from the extension.
- [**html_selector**](#agrag-loaders-ReadOptions-html_selector) (<code>str | None</code>) – The CSS selector for the main content of an HTML source.
- [**normalization**](#agrag-loaders-ReadOptions-normalization) (<code>[Normalization](../common/data_models/normalization/Normalization-ref.md)</code>) – How to normalize decoded text: byte-order mark, newline form
  and Unicode form. The default removes the mark, uses LF and applies NFKC.
  Chunk offsets index the normalized text.

## `csv_delimiter` \{#agrag-loaders-ReadOptions-csv_delimiter}

```python
csv_delimiter: str | None = None
```

## `csv_mode` \{#agrag-loaders-ReadOptions-csv_mode}

```python
csv_mode: CsvMode = CsvMode.ROWS
```

## `encoding` \{#agrag-loaders-ReadOptions-encoding}

```python
encoding: str | None = None
```

## `html_selector` \{#agrag-loaders-ReadOptions-html_selector}

```python
html_selector: str | None = None
```

## `id_column` \{#agrag-loaders-ReadOptions-id_column}

```python
id_column: str | None = None
```

## `json_mode` \{#agrag-loaders-ReadOptions-json_mode}

```python
json_mode: JsonMode = JsonMode.AUTO
```

## `max_document_bytes` \{#agrag-loaders-ReadOptions-max_document_bytes}

```python
max_document_bytes: int = 32 * 1024 * 1024
```

## `normalization` \{#agrag-loaders-ReadOptions-normalization}

```python
normalization: Normalization = field(default_factory=Normalization)
```

## `on_error` \{#agrag-loaders-ReadOptions-on_error}

```python
on_error: ErrorPolicy = ErrorPolicy.RAISE
```

## `store_raw_record` \{#agrag-loaders-ReadOptions-store_raw_record}

```python
store_raw_record: bool = False
```

## `store_text` \{#agrag-loaders-ReadOptions-store_text}

```python
store_text: bool = True
```

## `text_column` \{#agrag-loaders-ReadOptions-text_column}

```python
text_column: str | None = None
```

## `title_column` \{#agrag-loaders-ReadOptions-title_column}

```python
title_column: str | None = None
```
