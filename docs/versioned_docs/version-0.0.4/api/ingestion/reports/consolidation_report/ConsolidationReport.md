---
title: agrag.ingestion.reports.consolidation_report.ConsolidationReport
sidebar_label: ConsolidationReport
---

# `agrag.ingestion.reports.consolidation_report.ConsolidationReport` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport}

Bases: <code>BaseModel</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_match**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-would_match) (<code>list\[[MatchDecision](../../materialize/MatchDecision.md)\]</code>) – Confirmed non-exact matches found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-applied) (<code>bool</code>) – Whether the matches were materialized.
- [**failures**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failures) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Failures writing a match graph or resolved materialization.
  Always empty when apply is False.
- [**ambiguous_count**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.

## `ambiguous_count` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `applied` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-applied}

```python
applied: bool = False
```

## `failures` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `would_match` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-would_match}

```python
would_match: list[MatchDecision] = Field(default_factory=list)
```
