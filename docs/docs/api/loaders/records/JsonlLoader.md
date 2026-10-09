---
title: agrag.loaders.records.JsonlLoader
sidebar_label: JsonlLoader
---

# `agrag.loaders.records.JsonlLoader` \{#agrag-loaders-records-JsonlLoader}

Bases: <code>[RecordLoader](../base/RecordLoader.md)</code>

Reads JSON Lines files as one document per line.

A line that holds a JSON object becomes a record Document. A line that holds
another JSON value becomes a prose Document of its JSON text. With
`json_mode=DOCUMENT` the loader yields one prose Document for the whole
source.

**Attributes:**

- [**extensions**](#agrag-loaders-records-JsonlLoader-extensions) – The `.jsonl` and `.ndjson` extensions.

**Functions:**

- [**is_available**](#agrag-loaders-records-JsonlLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-records-JsonlLoader-load) – Yield one Document per non-blank line, or one for the whole source.

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

Yield one Document per non-blank line, or one for the whole source.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options. `json_mode=DOCUMENT` reads the whole source
  as one prose Document.
- **start_at** (<code>int</code>) – The record index to resume from.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document per non-blank line, in file order. A line that is a JSON
- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – object gives a record Document. A line with any other JSON value gives
- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – a prose Document.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – A line is not valid JSON.

## `mime_types` \{#agrag-loaders-records-JsonlLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
