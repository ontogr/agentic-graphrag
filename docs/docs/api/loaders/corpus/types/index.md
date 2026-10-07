---
title: agrag.loaders.corpus.types
sidebar_label: types
---

# `agrag.loaders.corpus.types` \{#agrag-loaders-corpus-types}

Plumbing types for the corpus loaders.

These types support the loader, decode, and walk machinery. They are feature-local to
`agrag.loaders.corpus` and are not domain models.

**Classes:**

- [**CsvMode**](CsvMode.md) – How to read a CSV or TSV source.
- [**DecodedText**](DecodedText.md) – Output of the four-step decode pipeline.
- [**ErrorPolicy**](ErrorPolicy.md) – The action to take when one source in a batch fails.
- [**IngestResult**](IngestResult.md) – The result of one ingest call.
- [**JsonMode**](JsonMode.md) – How to read a JSON source.
- [**LoadStats**](LoadStats.md) – Running tally of a corpus walk.
- [**LoaderCursor**](LoaderCursor.md) – Resume point for a corpus walk.
- [**ReadOptions**](ReadOptions.md) – Per-source reader configuration.
- [**SourceRef**](SourceRef.md) – A locatable input, before any bytes are read.
