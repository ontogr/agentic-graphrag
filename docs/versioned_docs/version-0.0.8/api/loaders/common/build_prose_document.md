---
title: agrag.loaders.common.build_prose_document
sidebar_label: build_prose_document
---

# `agrag.loaders.common.build_prose_document` \{#agrag-loaders-common-build_prose_document}

```python
build_prose_document(*, source:SourceRef, text:str, encoding:str, source_format:SourceFormat, loader_name:str, opts:ReadOptions, title:str, sections:list[DocumentSection] | None = None, source_hash:str | None = None, loader_version:str | None = None) -> Document
```

Build a prose-family Document from final text.

The content hash is the sha256 of `text`, so callers must pass the final
text (the extracted main content for HTML, the raw decoded text otherwise).

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source the text came from.
- **text** (<code>str</code>) – The final document text.
- **encoding** (<code>str</code>) – The encoding used to decode the source.
- **source_format** (<code>[SourceFormat](../../common/data_models/document/SourceFormat.md)</code>) – The format the loader used.
- **loader_name** (<code>str</code>) – The name to record for the loader.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options, used for the `store_text` flag.
- **title** (<code>str</code>) – The document title.
- **sections** (<code>list\[[DocumentSection](../../common/data_models/document/DocumentSection.md)\] | None</code>) – The sections of the document. Dropped when the read options do
  not store text, because their units point into the text.
- **source_hash** (<code>str | None</code>) – The sha256 of the raw source bytes. File loaders pass it;
  inline text has no source file and leaves it `None`.
- **loader_version** (<code>str | None</code>) – The version of the loader package, when known.

**Returns:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – The built Document.
