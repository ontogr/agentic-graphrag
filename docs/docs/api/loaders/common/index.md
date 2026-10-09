---
title: agrag.loaders.common
sidebar_label: common
---

# `agrag.loaders.common` \{#agrag-loaders-common}

Shared helpers for the corpus readers.

**Functions:**

- [**build_prose_document**](build_prose_document.md) – Build a prose-family Document from final text.
- [**build_record_document**](build_record_document.md) – Build a record-family Document from one row.
- [**paragraph_units**](paragraph_units.md) – Split text into paragraph units that point at their place in the document.
- [**read_within_limit**](read_within_limit.md) – Read a source's bytes without exceeding `max_document_bytes`.
- [**record_source_hash**](record_source_hash.md) – Hash the whole raw source bytes for a record-family document.
- [**resolve_text_column**](resolve_text_column.md) – Pick the column that holds document text.
- [**source_title**](source_title.md) – Derive a document title from the source uri.
- [**text_sections**](text_sections.md) – Return one section with an empty heading that holds the text as paragraphs.

**Attributes:**

- [**EXTENSION_FORMAT**](EXTENSION_FORMAT.md) (<code>dict\[str, [SourceFormat](../../common/data_models/document/SourceFormat.md)\]</code>) –
