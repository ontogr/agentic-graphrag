---
title: agrag.loaders.base.RecordLoader
sidebar_label: RecordLoader
---

# `agrag.loaders.base.RecordLoader` \{#agrag-loaders-base-RecordLoader}

Bases: <code>[Loader](Loader.md)</code>

A loader that makes one Document per record in a source.

Concrete readers read and decode the whole source into memory up front, up
to `opts.max_document_bytes`; that byte limit is what bounds memory use,
not incremental reads from disk. Whether records are parsed incrementally
from there is format-dependent: the CSV and JSONL readers parse and yield
one record at a time, so a malformed record later in the source surfaces
only after earlier records have already been yielded. The JSON reader
parses the whole source up front, so a malformed source fails before any
record is yielded.

**Functions:**

- [**is_available**](#agrag-loaders-base-RecordLoader-is_available) – Return whether the package that the loader's extra installs is present.
- [**load**](#agrag-loaders-base-RecordLoader-load) – Yield documents read from one source.

**Attributes:**

- [**extensions**](#agrag-loaders-base-RecordLoader-extensions) (<code>frozenset\[str\]</code>) –
- [**extra**](#agrag-loaders-base-RecordLoader-extra) (<code>str | None</code>) –
- [**extra_module**](#agrag-loaders-base-RecordLoader-extra_module) (<code>str | None</code>) –
- [**family**](#agrag-loaders-base-RecordLoader-family) –
- [**mime_types**](#agrag-loaders-base-RecordLoader-mime_types) (<code>frozenset\[str\]</code>) –

## `extensions` \{#agrag-loaders-base-RecordLoader-extensions}

```python
extensions: frozenset[str]
```

## `extra` \{#agrag-loaders-base-RecordLoader-extra}

```python
extra: str | None = None
```

## `extra_module` \{#agrag-loaders-base-RecordLoader-extra_module}

```python
extra_module: str | None = None
```

## `family` \{#agrag-loaders-base-RecordLoader-family}

```python
family = DocumentFamily.RECORD
```

## `is_available` \{#agrag-loaders-base-RecordLoader-is_available}

```python
is_available() -> bool
```

Return whether the package that the loader's extra installs is present.

A loader with no extra is always available. The check looks the module up
without importing it, so an installed package that fails to import still
counts.

## `load` \{#agrag-loaders-base-RecordLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield documents read from one source.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source, positioned at the start.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options for this call.
- **start_at** (<code>int</code>) – The record index to resume from. Prose loaders ignore this
  argument.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document per unit the source contains, in a fixed order.

## `mime_types` \{#agrag-loaders-base-RecordLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
