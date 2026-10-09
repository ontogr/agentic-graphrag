---
title: agrag.loaders.common.build_record_document
sidebar_label: build_record_document
---

# `agrag.loaders.common.build_record_document` \{#agrag-loaders-common-build_record_document}

```python
build_record_document(*, source:SourceRef, decoded:DecodedText, source_format:SourceFormat, loader_name:str, opts:ReadOptions, record_index:int, record:dict, source_hash:str, title:str) -> Document
```

Build a record-family Document from one row.

**Parameters:**

- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source the record came from.
- **decoded** (<code>[DecodedText](../types/DecodedText.md)</code>) – The decoded text and its metadata.
- **source_format** (<code>[SourceFormat](../../common/data_models/document/SourceFormat.md)</code>) – The format the loader used.
- **loader_name** (<code>str</code>) – The name to record for the loader.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options, used for the id, title, and text columns.
- **record_index** (<code>int</code>) – The 0-based row number.
- **record** (<code>dict</code>) – The parsed record data.
- **source_hash** (<code>str</code>) – The hash of the whole source file.
- **title** (<code>str</code>) – The fallback document title, used when `opts.title_column` is unset
  or absent from this record.

**Returns:**

- <code>[Document](../../common/data_models/document/Document-ref.md)</code> – The built Document.

**Raises:**

- <code>[MalformedRecordError](../errors/MalformedRecordError.md)</code> – `opts.id_column` is configured but missing, null, or
  blank in this record.
