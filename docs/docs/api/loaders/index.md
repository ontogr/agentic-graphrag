---
title: agrag.loaders
sidebar_position: 9
---


# `agrag.loaders` \{#agrag-loaders}

Document loaders: turn files, directories and raw text into Documents.

The docling loaders live in `agrag.loaders.docling`. PDF and image files need the
`docling` extra.

**Modules:**

- [**base**](base/index.md) – The Loader interface: reads one source and yields Document objects.
- [**chat**](chat/index.md) – Chat reader: JSON Lines or JSON messages, one section for each message.
- [**common**](common/index.md) – Shared helpers for the corpus readers.
- [**decode**](decode/index.md) – The four-step decode pipeline for source bytes.
- [**docling**](docling/index.md) – The docling loaders.
- [**errors**](errors/index.md) – Errors that the ingestion layer raises.
- [**loader_registry**](loader_registry/index.md) – The extension-to-loader registry.
- [**prose**](prose/index.md) – Prose readers: plain text and XML.
- [**records**](records/index.md) – Record readers: CSV, TSV, JSON Lines, and JSON.
- [**types**](types/index.md) – Plumbing types for the document loaders.
- [**walk**](walk/index.md) – Corpus walk, batching, and resumable streaming.

**Classes:**

- [**ChatLoader**](chat/ChatLoader.md) – Reads a file of chat messages as one document with a section for each message.
- [**CsvLoader**](records/CsvLoader.md) – Reads CSV and TSV files as one record document per row.
- [**DecodeError**](errors/DecodeError.md) – The source bytes do not decode to text.
- [**DocumentConversionError**](errors/DocumentConversionError.md) – A loader could not parse or convert a source's content.
- [**DocumentTooLargeError**](errors/DocumentTooLargeError.md) – A prose source is larger than the configured byte limit.
- [**ErrorPolicy**](types/ErrorPolicy.md) – The action to take when one source in a batch fails.
- [**IngestResult**](types/IngestResult.md) – The result of one ingest call.
- [**IngestionError**](errors/IngestionError.md) – The base class for every ingestion error.
- [**JsonLoader**](records/JsonLoader.md) – Reads JSON files, disambiguating arrays from objects.
- [**JsonlLoader**](records/JsonlLoader.md) – Reads JSON Lines files as one document per line.
- [**LoadStats**](types/LoadStats.md) – Running tally of a corpus walk.
- [**LoaderRegistry**](loader_registry/LoaderRegistry.md) – Maps a source extension to the loader that reads it.
- [**MalformedRecordError**](errors/MalformedRecordError.md) – One record in a record-family source does not parse.
- [**MissingExtraError**](errors/MissingExtraError.md) – A loader exists for this format, but its package extra is not installed.
- [**ReadOptions**](types/ReadOptions.md) – Per-source reader configuration.
- [**TextLoader**](prose/TextLoader.md) – Reads plain-text and log files as one document each.
- [**UnsupportedFormatError**](errors/UnsupportedFormatError.md) – No registered loader can read this source's format.
- [**XmlLoader**](prose/XmlLoader.md) – Reads an XML file as the text of its elements.

**Attributes:**

- [**registry**](loader_registry/registry.md) –
