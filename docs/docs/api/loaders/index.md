---
title: agrag.loaders
sidebar_position: 9
---


# `agrag.loaders` \{#agrag-loaders}

Document loaders: turn files, directories and raw text into Documents.

The docling loader needs the `docling` extra and lives in `agrag.loaders.docling`.

**Modules:**

- [**corpus**](corpus/index.md) – The corpus loaders package.
- [**docling**](docling/index.md) – The docling loader package.
- [**registry**](registry/index.md) – The extension-to-loader registry.

**Classes:**

- [**DecodeError**](DecodeError.md) – The source bytes do not decode to text.
- [**DocumentConversionError**](DocumentConversionError.md) – A loader could not parse or convert a source's content.
- [**DocumentTooLargeError**](DocumentTooLargeError.md) – A prose source is larger than the configured byte limit.
- [**ErrorPolicy**](ErrorPolicy.md) – The action to take when one source in a batch fails.
- [**IngestResult**](IngestResult.md) – The result of one ingest call.
- [**IngestionError**](IngestionError.md) – The base class for every ingestion error.
- [**LoadStats**](LoadStats.md) – Running tally of a corpus walk.
- [**LoaderRegistry**](LoaderRegistry.md) – Maps a source extension to the loader that reads it.
- [**MalformedRecordError**](MalformedRecordError.md) – One record in a record-family source does not parse.
- [**MissingExtraError**](MissingExtraError.md) – A loader exists for this format, but its package extra is not installed.
- [**ReadOptions**](ReadOptions.md) – Per-source reader configuration.
- [**UnsupportedFormatError**](UnsupportedFormatError.md) – No registered loader can read this source's format.
