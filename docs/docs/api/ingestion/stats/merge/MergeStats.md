---
title: agrag.ingestion.stats.merge.MergeStats
sidebar_label: MergeStats
---

# `agrag.ingestion.stats.merge.MergeStats` \{#agrag-ingestion-stats-merge-MergeStats}

Bases: <code>BaseModel</code>

Merge-stage results.

**Attributes:**

- [**nodes_created**](#agrag-ingestion-stats-merge-MergeStats-nodes_created) (<code>int</code>) – Brand-new entities created this call.
- [**nodes_updated**](#agrag-ingestion-stats-merge-MergeStats-nodes_updated) (<code>int</code>) – Existing entities that absorbed new mention data.
- [**conflicts_resolved**](#agrag-ingestion-stats-merge-MergeStats-conflicts_resolved) (<code>int</code>) – Total property/description conflicts resolved
  across every merge this call performed.
- [**failures**](#agrag-ingestion-stats-merge-MergeStats-failures) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Includes an LLM failure during description
  summarization. The merge still falls back to concatenation and
  completes, but the failure is recorded here. Also includes a
  failed read of a mention's persisted candidates: that mention
  is not merged in this call.
- [**failures_total**](#agrag-ingestion-stats-merge-MergeStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-merge-MergeStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

## `conflicts_resolved` \{#agrag-ingestion-stats-merge-MergeStats-conflicts_resolved}

```python
conflicts_resolved: int = 0
```

## `failures` \{#agrag-ingestion-stats-merge-MergeStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `failures_total` \{#agrag-ingestion-stats-merge-MergeStats-failures_total}

```python
failures_total: int = 0
```

## `failures_truncated` \{#agrag-ingestion-stats-merge-MergeStats-failures_truncated}

```python
failures_truncated: bool = False
```

## `nodes_created` \{#agrag-ingestion-stats-merge-MergeStats-nodes_created}

```python
nodes_created: int = 0
```

## `nodes_updated` \{#agrag-ingestion-stats-merge-MergeStats-nodes_updated}

```python
nodes_updated: int = 0
```
