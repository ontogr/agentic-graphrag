---
title: agrag.ingestion.stats.IngestStats
sidebar_label: IngestStats
---

# `agrag.ingestion.stats.IngestStats` \{#agrag-ingestion-stats-IngestStats}

Bases: <code>BaseModel</code>

Ingestion-stage results.

**Attributes:**

- [**documents**](#agrag-ingestion-stats-IngestStats-documents) (<code>int</code>) –
- [**quarantined**](#agrag-ingestion-stats-IngestStats-quarantined) (<code>int</code>) –
- [**quarantined_items**](#agrag-ingestion-stats-IngestStats-quarantined_items) (<code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code>) –
- [**skipped**](#agrag-ingestion-stats-IngestStats-skipped) (<code>int</code>) –
- [**sources**](#agrag-ingestion-stats-IngestStats-sources) (<code>int</code>) –

## `documents` \{#agrag-ingestion-stats-IngestStats-documents}

```python
documents: int = 0
```

## `quarantined` \{#agrag-ingestion-stats-IngestStats-quarantined}

```python
quarantined: int = 0
```

## `quarantined_items` \{#agrag-ingestion-stats-IngestStats-quarantined_items}

```python
quarantined_items: list[StageFailure] = Field(default_factory=list)
```

## `skipped` \{#agrag-ingestion-stats-IngestStats-skipped}

```python
skipped: int = 0
```

## `sources` \{#agrag-ingestion-stats-IngestStats-sources}

```python
sources: int = 0
```
