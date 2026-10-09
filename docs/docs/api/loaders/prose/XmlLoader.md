---
title: agrag.loaders.prose.XmlLoader
sidebar_label: XmlLoader
---

# `agrag.loaders.prose.XmlLoader` \{#agrag-loaders-prose-XmlLoader}

Bases: <code>[ProseLoader](../base/ProseLoader.md)</code>

Reads an XML file as the text of its elements.

The loader drops the tags and joins the text it finds with newlines. Text in
an element with mixed content is split at its child elements. Text inside a
CDATA section is not kept.

**Attributes:**

- [**extensions**](#agrag-loaders-prose-XmlLoader-extensions) – The `.xml` extension.

**Functions:**

- [**is_available**](#agrag-loaders-prose-XmlLoader-is_available) – Return whether the package that the loader's extra installs is present.
- [**load**](#agrag-loaders-prose-XmlLoader-load) – Yield one prose Document from the text of the elements.

## `extensions` \{#agrag-loaders-prose-XmlLoader-extensions}

```python
extensions = frozenset({'.xml'})
```

## `extra` \{#agrag-loaders-prose-XmlLoader-extra}

```python
extra: str | None = None
```

## `extra_module` \{#agrag-loaders-prose-XmlLoader-extra_module}

```python
extra_module: str | None = None
```

## `family` \{#agrag-loaders-prose-XmlLoader-family}

```python
family = DocumentFamily.PROSE
```

## `is_available` \{#agrag-loaders-prose-XmlLoader-is_available}

```python
is_available() -> bool
```

Return whether the package that the loader's extra installs is present.

A loader with no extra is always available. The check looks the module up
without importing it, so an installed package that fails to import still
counts.

## `load` \{#agrag-loaders-prose-XmlLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document from the text of the elements.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options for this call.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – One Document holding the element text.

## `mime_types` \{#agrag-loaders-prose-XmlLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
