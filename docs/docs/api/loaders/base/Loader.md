---
title: agrag.loaders.base.Loader
sidebar_label: Loader
---

# `agrag.loaders.base.Loader` \{#agrag-loaders-base-Loader}

Bases: <code>ABC</code>

Reads one source and yields Document objects.

A Loader keeps no state between calls, so a worker process can reuse one instance
across many sources.

**Attributes:**

- [**extensions**](#agrag-loaders-base-Loader-extensions) (<code>frozenset\[str\]</code>) – The file extensions this loader claims, each with a leading dot.
- [**mime_types**](#agrag-loaders-base-Loader-mime_types) (<code>frozenset\[str\]</code>) – The MIME types this loader claims. Empty when the loader relies on
  the extension alone.
- [**family**](#agrag-loaders-base-Loader-family) (<code>[DocumentFamily](../../common/data_models/document/DocumentFamily.md)</code>) – The document family this loader produces.
- [**extra**](#agrag-loaders-base-Loader-extra) (<code>str | None</code>) – The package extra this loader needs. `None` for core loaders. The
  registry raises MissingExtraError for a loader whose extra is not
  installed.
- [**extra_module**](#agrag-loaders-base-Loader-extra_module) (<code>str | None</code>) – The importable module that proves the extra is installed.
  `None` means the module has the same name as `extra`.

**Functions:**

- [**is_available**](#agrag-loaders-base-Loader-is_available) – Return whether the package that the loader's extra installs is present.
- [**load**](#agrag-loaders-base-Loader-load) – Yield documents read from one source.

## `extensions` \{#agrag-loaders-base-Loader-extensions}

```python
extensions: frozenset[str]
```

## `extra` \{#agrag-loaders-base-Loader-extra}

```python
extra: str | None = None
```

## `extra_module` \{#agrag-loaders-base-Loader-extra_module}

```python
extra_module: str | None = None
```

## `family` \{#agrag-loaders-base-Loader-family}

```python
family: DocumentFamily
```

## `is_available` \{#agrag-loaders-base-Loader-is_available}

```python
is_available() -> bool
```

Return whether the package that the loader's extra installs is present.

A loader with no extra is always available. The check looks the module up
without importing it, so an installed package that fails to import still
counts.

## `load` \{#agrag-loaders-base-Loader-load}

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

## `mime_types` \{#agrag-loaders-base-Loader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
