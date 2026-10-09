---
title: agrag.loaders.prose.TextLoader
sidebar_label: TextLoader
---

# `agrag.loaders.prose.TextLoader` \{#agrag-loaders-prose-TextLoader}

Bases: <code>[ProseLoader](../base/ProseLoader.md)</code>

Reads plain-text and log files as one document each.

**Attributes:**

- [**extensions**](#agrag-loaders-prose-TextLoader-extensions) – The `.txt` and `.log` extensions.

**Functions:**

- [**is_available**](#agrag-loaders-prose-TextLoader-is_available) – Return whether the package that the loader's extra installs is present.
- [**load**](#agrag-loaders-prose-TextLoader-load) – Yield one prose Document from the source.

## `extensions` \{#agrag-loaders-prose-TextLoader-extensions}

```python
extensions = frozenset({'.txt', '.log'})
```

## `extra` \{#agrag-loaders-prose-TextLoader-extra}

```python
extra: str | None = None
```

## `extra_module` \{#agrag-loaders-prose-TextLoader-extra_module}

```python
extra_module: str | None = None
```

## `family` \{#agrag-loaders-prose-TextLoader-family}

```python
family = DocumentFamily.PROSE
```

## `is_available` \{#agrag-loaders-prose-TextLoader-is_available}

```python
is_available() -> bool
```

Return whether the package that the loader's extra installs is present.

A loader with no extra is always available. The check looks the module up
without importing it, so an installed package that fails to import still
counts.

## `load` \{#agrag-loaders-prose-TextLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document from the source.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options for this call.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document holding the decoded text.

## `mime_types` \{#agrag-loaders-prose-TextLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
