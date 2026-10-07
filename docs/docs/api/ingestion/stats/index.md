---
title: agrag.ingestion.stats
sidebar_label: stats
---

# `agrag.ingestion.stats` \{#agrag-ingestion-stats}

Per-stage observability types for the ingestion pipeline.

One class per module under this package; this init re-exports them so
`from agrag.ingestion.stats import ExtractionStats` keeps working.
`StageFailure`/`CappedFailures`/`cap_failures`/`MAX_FAILURES_PER_STAGE`
live in `agrag.common.data_models.stage_failure` -- a shared model used
outside the ingestion pipeline too -- and are not re-exported here.

**Modules:**

- [**chunking**](chunking/index.md) – Chunking-stage stats.
- [**extraction**](extraction/index.md) – Extraction-stage stats.
- [**ingest**](ingest/index.md) – Ingestion-stage stats.
- [**merge**](merge/index.md) – Merge-stage stats.
- [**resolution**](resolution/index.md) – Resolution-stage stats.
- [**storage**](storage/index.md) – Storage-write-stage stats.

**Classes:**

- [**ChunkingMatch**](ChunkingMatch.md) – The chunker that one document got, and what it produced.
- [**ChunkingStats**](ChunkingStats.md) – Chunking-stage results.
- [**ExtractionStats**](ExtractionStats.md) – Extraction-stage results.
- [**IngestStats**](IngestStats.md) – Ingestion-stage results.
- [**MergeStats**](MergeStats.md) – Merge-stage results.
- [**ResolutionStats**](ResolutionStats.md) – Resolution-stage results.
- [**StorageStats**](StorageStats.md) – Storage-write-stage results.
