---
title: agrag.loaders.base.ProseLoader
sidebar_label: ProseLoader
---

# `agrag.loaders.base.ProseLoader` \{#agrag-loaders-base-ProseLoader}

Bases: <code>[Loader](Loader.md)</code>

A loader that makes one Document per source.

Concrete readers reject a source larger than the configured byte limit when the
source's byte size is known upfront (`SourceRef.byte_size` is not `None`).

**Functions:**

- [**is_available**](#agrag-loaders-base-ProseLoader-is_available) – Return whether the package that the loader's extra installs is present.
- [**load**](#agrag-loaders-base-ProseLoader-load) – Yield documents read from one source.

**Attributes:**

- [**extensions**](#agrag-loaders-base-ProseLoader-extensions) (<code>frozenset\[str\]</code>) –
- [**extra**](#agrag-loaders-base-ProseLoader-extra) (<code>str | None</code>) –
- [**extra_module**](#agrag-loaders-base-ProseLoader-extra_module) (<code>str | None</code>) –
- [**family**](#agrag-loaders-base-ProseLoader-family) –
- [**mime_types**](#agrag-loaders-base-ProseLoader-mime_types) (<code>frozenset\[str\]</code>) –

## `extensions` \{#agrag-loaders-base-ProseLoader-extensions}

```python
extensions: frozenset[str]
```

## `extra` \{#agrag-loaders-base-ProseLoader-extra}

```python
extra: str | None = None
```

## `extra_module` \{#agrag-loaders-base-ProseLoader-extra_module}

```python
extra_module: str | None = None
```

## `family` \{#agrag-loaders-base-ProseLoader-family}

```python
family = DocumentFamily.PROSE
```

## `is_available` \{#agrag-loaders-base-ProseLoader-is_available}

```python
is_available() -> bool
```

Return whether the package that the loader's extra installs is present.

A loader with no extra is always available. The check looks the module up
without importing it, so an installed package that fails to import still
counts.

## `load` \{#agrag-loaders-base-ProseLoader-load}

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

## `mime_types` \{#agrag-loaders-base-ProseLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
