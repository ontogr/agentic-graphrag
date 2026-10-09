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

- [**is_available**](#agrag-loaders-prose-XmlLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-prose-XmlLoader-load) – Yield one prose Document from the text of the elements.

## `extensions` \{#agrag-loaders-prose-XmlLoader-extensions}

```python
extensions = frozenset({'.xml'})
```

## `extra` \{#agrag-loaders-prose-XmlLoader-extra}

```python
extra: str | None = None
```

## `family` \{#agrag-loaders-prose-XmlLoader-family}

```python
family = DocumentFamily.PROSE
```

## `is_available` \{#agrag-loaders-prose-XmlLoader-is_available}

```python
is_available() -> bool
```

Return whether this loader can run in this process.

A loader with no extra is always available. A loader with an extra is
available when its package can be found. The check does not import the
package, so an installed package that fails to import still counts.

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
