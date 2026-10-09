---
title: agrag.loaders.errors
sidebar_label: errors
---

# `agrag.loaders.errors` \{#agrag-loaders-errors}

Errors that the ingestion layer raises.

**Classes:**

- [**DecodeError**](DecodeError.md) – The source bytes do not decode to text.
- [**DocumentConversionError**](DocumentConversionError.md) – A loader could not parse or convert a source's content.
- [**DocumentTooLargeError**](DocumentTooLargeError.md) – A prose source is larger than the configured byte limit.
- [**IngestionError**](IngestionError.md) – The base class for every ingestion error.
- [**MalformedRecordError**](MalformedRecordError.md) – One record in a record-family source does not parse.
- [**MissingExtraError**](MissingExtraError.md) – A loader exists for this format, but its package extra is not installed.
- [**UnsupportedFormatError**](UnsupportedFormatError.md) – No registered loader can read this source's format.
