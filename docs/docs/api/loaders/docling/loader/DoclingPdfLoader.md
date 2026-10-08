---
title: agrag.loaders.docling.loader.DoclingPdfLoader
sidebar_label: DoclingPdfLoader
---

# `agrag.loaders.docling.loader.DoclingPdfLoader` \{#agrag-loaders-docling-loader-DoclingPdfLoader}

Bases: <code>[DoclingLoader](DoclingLoader.md)</code>

Reads PDF and image files with docling.

PDF needs the `docling` extra, which installs the layout and table models. The
loader runs OCR on a PDF only where the PDF has no text layer. It reads heading
depth from the bookmarks of the PDF. A PDF with no bookmarks whose headings carry
dotted numbers gets its depth from the numbers.

**Attributes:**

- [**extensions**](#agrag-loaders-docling-loader-DoclingPdfLoader-extensions) – The PDF and image formats this loader reads.
- [**extra**](#agrag-loaders-docling-loader-DoclingPdfLoader-extra) – The package extra that installs the models.
- [**extra_module**](#agrag-loaders-docling-loader-DoclingPdfLoader-extra_module) – A module that only the extra installs.

**Functions:**

- [**load**](#agrag-loaders-docling-loader-DoclingPdfLoader-load) – Yield one prose Document parsed by docling.

## `extensions` \{#agrag-loaders-docling-loader-DoclingPdfLoader-extensions}

```python
extensions = frozenset(_PDF_FORMATS)
```

## `extra` \{#agrag-loaders-docling-loader-DoclingPdfLoader-extra}

```python
extra = 'docling'
```

## `extra_module` \{#agrag-loaders-docling-loader-DoclingPdfLoader-extra_module}

```python
extra_module = 'docling_ibm_models'
```

## `family` \{#agrag-loaders-docling-loader-DoclingPdfLoader-family}

```python
family = DocumentFamily.PROSE
```

## `load` \{#agrag-loaders-docling-loader-DoclingPdfLoader-load}

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

- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – One Document. Its text is the docling Markdown export, and its sections
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – hold the content. Its title is the first heading, or the file name when
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – the source has no heading.

**Raises:**

- <code>[DocumentTooLargeError](../../corpus/errors/DocumentTooLargeError.md)</code> – The source is larger than the configured byte
  limit.
- <code>[DocumentConversionError](../../corpus/errors/DocumentConversionError.md)</code> – Docling could not parse or convert the source.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.

## `mime_types` \{#agrag-loaders-docling-loader-DoclingPdfLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
