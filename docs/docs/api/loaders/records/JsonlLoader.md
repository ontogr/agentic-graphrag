---
title: agrag.loaders.records.JsonlLoader
sidebar_label: JsonlLoader
---

# `agrag.loaders.records.JsonlLoader` \{#agrag-loaders-records-JsonlLoader}

Bases: <code>[RecordLoader](../base/RecordLoader.md)</code>

Reads JSON Lines files as one document per line.

**Attributes:**

- [**extensions**](#agrag-loaders-records-JsonlLoader-extensions) – The `.jsonl` and `.ndjson` extensions.

**Functions:**

- [**is_available**](#agrag-loaders-records-JsonlLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-records-JsonlLoader-load) – Yield one record Document per JSON object.

## `extensions` \{#agrag-loaders-records-JsonlLoader-extensions}

```python
extensions = frozenset({'.jsonl', '.ndjson'})
```

## `extra` \{#agrag-loaders-records-JsonlLoader-extra}

```python
extra: str | None = None
```

## `family` \{#agrag-loaders-records-JsonlLoader-family}

```python
family = DocumentFamily.RECORD
```

## `is_available` \{#agrag-loaders-records-JsonlLoader-is_available}

```python
is_available() -> bool
```

Return whether this loader can run in this process.

A loader with no extra is always available. A loader with an extra is
available when its package can be found. The check does not import the
package, so an installed package that fails to import still counts.

## `load` \{#agrag-loaders-records-JsonlLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one record Document per JSON object.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options.
- **start_at** (<code>int</code>) – The record index to resume from.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document per line, in file order.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – A line is not valid JSON.

## `mime_types` \{#agrag-loaders-records-JsonlLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
