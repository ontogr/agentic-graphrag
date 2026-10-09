---
title: agrag.loaders.records.CsvLoader
sidebar_label: CsvLoader
---

# `agrag.loaders.records.CsvLoader` \{#agrag-loaders-records-CsvLoader}

Bases: <code>[RecordLoader](../base/RecordLoader.md)</code>

Reads CSV and TSV files as one document per row.

**Attributes:**

- [**extensions**](#agrag-loaders-records-CsvLoader-extensions) – The `.csv` and `.tsv` extensions.

**Functions:**

- [**is_available**](#agrag-loaders-records-CsvLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-records-CsvLoader-load) – Yield one record Document per row.

## `extensions` \{#agrag-loaders-records-CsvLoader-extensions}

```python
extensions = frozenset({'.csv', '.tsv'})
```

## `extra` \{#agrag-loaders-records-CsvLoader-extra}

```python
extra: str | None = None
```

## `family` \{#agrag-loaders-records-CsvLoader-family}

```python
family = DocumentFamily.RECORD
```

## `is_available` \{#agrag-loaders-records-CsvLoader-is_available}

```python
is_available() -> bool
```

Return whether this loader can run in this process.

A loader with no extra is always available. A loader with an extra is
available when its package can be found. The check does not import the
package, so an installed package that fails to import still counts.

## `load` \{#agrag-loaders-records-CsvLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one record Document per row.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options. `csv_delimiter` overrides the separator.
- **start_at** (<code>int</code>) – The record index to resume from.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document per row, in file order.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – A row fails to parse.

## `mime_types` \{#agrag-loaders-records-CsvLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
