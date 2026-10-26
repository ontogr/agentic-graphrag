---
title: agrag.ingestion.reports.conversion_report.ConversionReport
sidebar_label: ConversionReport
---

# `agrag.ingestion.reports.conversion_report.ConversionReport` \{#agrag-ingestion-reports-conversion_report-ConversionReport}

Bases: <code>BaseModel</code>

What a candidate conversion did.

**Attributes:**

- [**converted_entities**](#agrag-ingestion-reports-conversion_report-ConversionReport-converted_entities) (<code>int</code>) – Entity candidates converted in place.
- [**folded**](#agrag-ingestion-reports-conversion_report-ConversionReport-folded) (<code>int</code>) – Entity candidates folded into an existing exact-name owner.
- [**created_relations**](#agrag-ingestion-reports-conversion_report-ConversionReport-created_relations) (<code>int</code>) – Relation candidates written as edges.
- [**set_properties**](#agrag-ingestion-reports-conversion_report-ConversionReport-set_properties) (<code>int</code>) – Property candidates written on their entities.
- [**skipped**](#agrag-ingestion-reports-conversion_report-ConversionReport-skipped) (<code>dict\[str, str\]</code>) – Candidate ids that were not converted and their reason.
- [**failures**](#agrag-ingestion-reports-conversion_report-ConversionReport-failures) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Post-commit vector mirror or embedding failures.

## `converted_entities` \{#agrag-ingestion-reports-conversion_report-ConversionReport-converted_entities}

```python
converted_entities: int = 0
```

## `created_relations` \{#agrag-ingestion-reports-conversion_report-ConversionReport-created_relations}

```python
created_relations: int = 0
```

## `failures` \{#agrag-ingestion-reports-conversion_report-ConversionReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `folded` \{#agrag-ingestion-reports-conversion_report-ConversionReport-folded}

```python
folded: int = 0
```

## `set_properties` \{#agrag-ingestion-reports-conversion_report-ConversionReport-set_properties}

```python
set_properties: int = 0
```

## `skipped` \{#agrag-ingestion-reports-conversion_report-ConversionReport-skipped}

```python
skipped: dict[str, str] = Field(default_factory=dict)
```
