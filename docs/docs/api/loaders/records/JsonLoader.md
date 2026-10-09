---
title: agrag.loaders.records.JsonLoader
sidebar_label: JsonLoader
---

# `agrag.loaders.records.JsonLoader` \{#agrag-loaders-records-JsonLoader}

Bases: <code>[RecordLoader](../base/RecordLoader.md)</code>

Reads JSON files, disambiguating arrays from objects.

**Attributes:**

- [**extensions**](#agrag-loaders-records-JsonLoader-extensions) – The `.json` extension.

**Functions:**

- [**is_available**](#agrag-loaders-records-JsonLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-records-JsonLoader-load) – Yield documents from a JSON source.

## `extensions` \{#agrag-loaders-records-JsonLoader-extensions}

```python
extensions = frozenset({'.json'})
```

## `extra` \{#agrag-loaders-records-JsonLoader-extra}

```python
extra: str | None = None
```

## `family` \{#agrag-loaders-records-JsonLoader-family}

```python
family = DocumentFamily.RECORD
```

## `is_available` \{#agrag-loaders-records-JsonLoader-is_available}

```python
is_available() -> bool
```

Return whether this loader can run in this process.

A loader with no extra is always available. A loader with an extra is
available when its package can be found. The check does not import the
package, so an installed package that fails to import still counts.

## `load` \{#agrag-loaders-records-JsonLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield documents from a JSON source.

A top-level array becomes one record Document per element, unless `json_mode`
is
`DOCUMENT`, which yields one prose Document holding the whole array. A
top-level
object becomes one prose Document.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options. `json_mode` overrides the sniff.
- **start_at** (<code>int</code>) – The record index to resume from (arrays only).

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One or more Documents, in file order.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – The source is not valid JSON.

## `mime_types` \{#agrag-loaders-records-JsonLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
