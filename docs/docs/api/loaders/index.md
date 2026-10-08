---
title: agrag.loaders
sidebar_position: 9
---


# `agrag.loaders` \{#agrag-loaders}

Document loaders: turn files, directories and raw text into Documents.

The docling loaders live in `agrag.loaders.docling`. PDF and image files need the
`docling` extra.

**Modules:**

- [**corpus**](corpus/index.md) – The corpus loaders package.
- [**docling**](docling/index.md) – The docling loaders.
- [**registry**](registry/index.md) – The extension-to-loader registry.

**Classes:**

- [**DecodeError**](corpus/errors/DecodeError.md) – The source bytes do not decode to text.
- [**DocumentConversionError**](corpus/errors/DocumentConversionError.md) – A loader could not parse or convert a source's content.
- [**DocumentTooLargeError**](corpus/errors/DocumentTooLargeError.md) – A prose source is larger than the configured byte limit.
- [**ErrorPolicy**](corpus/types/ErrorPolicy.md) – The action to take when one source in a batch fails.
- [**IngestResult**](corpus/types/IngestResult.md) – The result of one ingest call.
- [**IngestionError**](corpus/errors/IngestionError.md) – The base class for every ingestion error.
- [**LoadStats**](corpus/types/LoadStats.md) – Running tally of a corpus walk.
- [**LoaderRegistry**](corpus/registry/LoaderRegistry.md) – Maps a source extension to the loader that reads it.
- [**MalformedRecordError**](corpus/errors/MalformedRecordError.md) – One record in a record-family source does not parse.
- [**MissingExtraError**](corpus/errors/MissingExtraError.md) – A loader exists for this format, but its package extra is not installed.
- [**ReadOptions**](corpus/types/ReadOptions.md) – Per-source reader configuration.
- [**UnsupportedFormatError**](corpus/errors/UnsupportedFormatError.md) – No registered loader can read this source's format.
