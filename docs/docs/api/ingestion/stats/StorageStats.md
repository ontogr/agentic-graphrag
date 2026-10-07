---
title: agrag.ingestion.stats.StorageStats
sidebar_label: StorageStats
---

# `agrag.ingestion.stats.StorageStats` \{#agrag-ingestion-stats-StorageStats}

Bases: <code>BaseModel</code>

Storage-write-stage results.

**Attributes:**

- [**nodes_written**](#agrag-ingestion-stats-StorageStats-nodes_written) (<code>int</code>) – Chunk and Entity nodes together, one aggregate
  count rather than a sub-count per kind — both are written in
  the same final phase, so there is one natural accounting
  point.
- [**relationships_written**](#agrag-ingestion-stats-StorageStats-relationships_written) (<code>int</code>) – Domain Relation and MENTIONED_IN edges
  together, for the same reason.
- [**failures**](#agrag-ingestion-stats-StorageStats-failures) (<code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Isolated graph-write failures are reported per record and
  capped per call. Conversion, embedding, vector-store, and other
  non-isolatable graph failures can use one stage-level failure.
  The counts include only records that landed.
- [**failures_total**](#agrag-ingestion-stats-StorageStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-StorageStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

## `failures` \{#agrag-ingestion-stats-StorageStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `failures_total` \{#agrag-ingestion-stats-StorageStats-failures_total}

```python
failures_total: int = 0
```

## `failures_truncated` \{#agrag-ingestion-stats-StorageStats-failures_truncated}

```python
failures_truncated: bool = False
```

## `nodes_written` \{#agrag-ingestion-stats-StorageStats-nodes_written}

```python
nodes_written: int = 0
```

## `relationships_written` \{#agrag-ingestion-stats-StorageStats-relationships_written}

```python
relationships_written: int = 0
```
