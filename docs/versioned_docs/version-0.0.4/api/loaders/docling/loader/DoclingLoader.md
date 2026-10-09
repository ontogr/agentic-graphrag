---
title: agrag.loaders.docling.loader.DoclingLoader
sidebar_label: DoclingLoader
---

# `agrag.loaders.docling.loader.DoclingLoader` \{#agrag-loaders-docling-loader-DoclingLoader}

Bases: <code>[ProseLoader](../../corpus/base/ProseLoader.md)</code>

Reads documents with the docling library.

This loader registers for the PDF, DOCX, PPTX, and image formats, plus the Markdown,
HTML, CSV, AsciiDoc, and XML formats it can also parse. It wins by default only for
the
formats no core loader claims.

**Attributes:**

- [**extensions**](#agrag-loaders-docling-loader-DoclingLoader-extensions) – Every format docling can read.
- [**extra**](#agrag-loaders-docling-loader-DoclingLoader-extra) – The package extra required to use this loader.

**Functions:**

- [**load**](#agrag-loaders-docling-loader-DoclingLoader-load) – Yield one prose Document parsed by docling.

## `extensions` \{#agrag-loaders-docling-loader-DoclingLoader-extensions}

```python
extensions = frozenset(_DOCLING_FORMATS.keys())
```

## `extra` \{#agrag-loaders-docling-loader-DoclingLoader-extra}

```python
extra = 'docling'
```

## `family` \{#agrag-loaders-docling-loader-DoclingLoader-family}

```python
family = DocumentFamily.PROSE
```

## `load` \{#agrag-loaders-docling-loader-DoclingLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document parsed by docling.

The content hash comes from the raw source bytes, not from docling's parsed
output,
because the parsed output can change between docling versions and runs.

**Parameters:**

- **source** (<code>[SourceRef](../../corpus/types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../../corpus/types/ReadOptions.md)</code>) – The read options.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – One Document holding docling's Markdown export of the source.

**Raises:**

- <code>[MissingExtraError](../../corpus/errors/MissingExtraError.md)</code> – The docling extra is not installed.
- <code>[DocumentTooLargeError](../../corpus/errors/DocumentTooLargeError.md)</code> – The source is larger than the configured byte
  limit.
- <code>[DocumentConversionError](../../corpus/errors/DocumentConversionError.md)</code> – Docling could not parse or convert the source.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.

## `mime_types` \{#agrag-loaders-docling-loader-DoclingLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
