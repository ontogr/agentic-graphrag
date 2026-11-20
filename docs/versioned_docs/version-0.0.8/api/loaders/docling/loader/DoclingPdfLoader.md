---
title: agrag.loaders.docling.loader.DoclingPdfLoader
sidebar_label: DoclingPdfLoader
---

# `agrag.loaders.docling.loader.DoclingPdfLoader` \{#agrag-loaders-docling-loader-DoclingPdfLoader}

Bases: <code>[DoclingLoader](DoclingLoader.md)</code>

Reads PDF and image files with docling.

PDF needs the `docling` extra, which installs the layout and table models. The
loader runs OCR on a PDF only where the PDF has no text layer, except for a PDF
with at least 80% of pages lacking text, which gets full-page OCR. It reads
heading depth from the bookmarks of the PDF. A PDF with no bookmarks whose
headings carry dotted numbers gets its depth from the numbers.

**Attributes:**

- [**extensions**](#agrag-loaders-docling-loader-DoclingPdfLoader-extensions) – The PDF and image formats this loader reads.
- [**extra**](#agrag-loaders-docling-loader-DoclingPdfLoader-extra) – The package extra that installs the models.
- [**extra_module**](#agrag-loaders-docling-loader-DoclingPdfLoader-extra_module) – The model package that only the extra installs. The core
  docling package is present without the extra, so it cannot prove the
  extra is installed.

**Functions:**

- [**is_available**](#agrag-loaders-docling-loader-DoclingPdfLoader-is_available) – Return whether the package that the loader's extra installs is present.
- [**load**](#agrag-loaders-docling-loader-DoclingPdfLoader-load) – Yield one prose Document parsed by docling.

## `extensions` \{#agrag-loaders-docling-loader-DoclingPdfLoader-extensions}

```python
extensions = frozenset(_formats)
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

## `is_available` \{#agrag-loaders-docling-loader-DoclingPdfLoader-is_available}

```python
is_available() -> bool
```

Return whether the package that the loader's extra installs is present.

A loader with no extra is always available. The check looks the module up
without importing it, so an installed package that fails to import still
counts.

## `load` \{#agrag-loaders-docling-loader-DoclingPdfLoader-load}

```python
load(source:SourceRef, stream:BinaryIO, opts:ReadOptions, *, start_at:int = 0) -> Iterator[Document]
```

Yield one prose Document parsed by docling.

**Parameters:**

- **source** (<code>[SourceRef](../../types/SourceRef.md)</code>) – The source to read.
- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **opts** (<code>[ReadOptions](../../types/ReadOptions.md)</code>) – The read options.
- **start_at** (<code>int</code>) – Ignored by prose loaders.

**Yields:**

- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – One Document. When `opts.store_text` is on, its text is the docling
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – Markdown export and its sections hold the content; with the flag off
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – both are empty. Its title is the first heading, or the file name when
- <code>[Document](../../../common/data_models/document/Document-ref.md)</code> – the source has no heading.

**Raises:**

- <code>[DocumentTooLargeError](../../errors/DocumentTooLargeError.md)</code> – The source is larger than the configured byte
  limit.
- <code>[MissingExtraError](../../errors/MissingExtraError.md)</code> – `DoclingPdfLoader` only. A package that docling
  needs is not installed, and the error names the `docling` extra.
  It is an `UnsupportedFormatError`, so SKIP and QUARANTINE treat
  it like an unsupported format.
- <code>ImportError</code> – `DoclingLoader` only. A package that docling needs is
  not installed. This is an install problem, not a problem with the
  source, so the walker policies do not catch it.
- <code>[DocumentConversionError](../../errors/DocumentConversionError.md)</code> – Docling or its export failed on the source,
  for any other reason. Walker policies such as SKIP and QUARANTINE
  catch this error.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.

## `mime_types` \{#agrag-loaders-docling-loader-DoclingPdfLoader-mime_types}

```python
mime_types: frozenset[str] = frozenset()
```
