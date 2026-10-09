---
title: agrag.loaders.docling.loader.DoclingLoader
sidebar_label: DoclingLoader
---

# `agrag.loaders.docling.loader.DoclingLoader` \{#agrag-loaders-docling-loader-DoclingLoader}

Bases: <code>[ProseLoader](../../corpus/base/ProseLoader.md)</code>

Reads Markdown, HTML, AsciiDoc, DOCX, PPTX and XLSX files with docling.

The loader gives a document its sections from the structure that docling finds. It
needs no model and no extra. The content hash comes from the raw source bytes,
because the parsed output can change between docling versions and runs.

**Attributes:**

- [**extensions**](#agrag-loaders-docling-loader-DoclingLoader-extensions) – The formats this loader reads.

**Functions:**

- [**is_available**](#agrag-loaders-docling-loader-DoclingLoader-is_available) – Return whether this loader can run in this process.
- [**load**](#agrag-loaders-docling-loader-DoclingLoader-load) – Yield one prose Document parsed by docling.

## `extensions` \{#agrag-loaders-docling-loader-DoclingLoader-extensions}

```python
extensions = frozenset(_formats)
```

## `extra` \{#agrag-loaders-docling-loader-DoclingLoader-extra}

```python
extra: str | None = None
```

## `family` \{#agrag-loaders-docling-loader-DoclingLoader-family}

```python
family = DocumentFamily.PROSE
```

## `is_available` \{#agrag-loaders-docling-loader-DoclingLoader-is_available}

```python
is_available() -> bool
```

Return whether this loader can run in this process.

A loader with no extra is always available. A loader with an extra is
available when its package can be found. The check does not import the
package, so an installed package that fails to import still counts.

## `load` \{#agrag-loaders-docling-loader-DoclingLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document parsed by docling.

**Parameters:**

- **source** (<code>[SourceRef](../../corpus/types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../../corpus/types/ReadOptions.md)</code>) – The read options.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – One Document. When `opts.store_text` is on, its text is the docling
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – Markdown export and its sections hold the content; with the flag off
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – both are empty. Its title is the first heading, or the file name when
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – the source has no heading.

**Raises:**

- <code>[DocumentTooLargeError](../../corpus/errors/DocumentTooLargeError.md)</code> – The source is larger than the configured byte
  limit.
- <code>[DocumentConversionError](../../corpus/errors/DocumentConversionError.md)</code> – Docling could not parse or convert the source.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.

## `mime_types` \{#agrag-loaders-docling-loader-DoclingLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
