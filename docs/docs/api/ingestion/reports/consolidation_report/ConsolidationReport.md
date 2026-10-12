---
title: agrag.ingestion.reports.consolidation_report.ConsolidationReport
sidebar_label: ConsolidationReport
---

# `agrag.ingestion.reports.consolidation_report.ConsolidationReport` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport}

Bases: <code>BaseModel</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_match**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-would_match) (<code>list\[[MatchDecision](../../resolved_entities/MatchDecision.md)\]</code>) – Confirmed non-exact matches found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-applied) (<code>bool</code>) – Whether the matches were applied.
- [**failures**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failures) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Failures reading the candidates of an entity, which that
  entity then skips, and failures writing a match graph or
  rebuilding resolved entities. Only the candidate read failures
  appear when apply is False.
- [**ambiguous_count**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-ambiguous_count) (<code>int</code>) – LLM answers that were uncertain, missing, or
  malformed. These pairs never merge.
- [**failed_llm_requests**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failed_llm_requests) (<code>int</code>) – LLM verification requests that raised, summed
  over all labels. Their pairs are undecided and not merged.
- [**cap_truncated_pairs**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-cap_truncated_pairs) (<code>int</code>) – Ambiguous pairs over the per-label cap
  (`max_llm_pairs`), summed over all labels. They never reached
  the LLM.
- [**llm_unavailable_pairs**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-llm_unavailable_pairs) (<code>int</code>) – Ambiguous pairs that never reached the LLM
  because no LLM settings were found, summed over all labels.

## `ambiguous_count` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `applied` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-applied}

```python
applied: bool = False
```

## `cap_truncated_pairs` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

## `failed_llm_requests` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `failures` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `llm_unavailable_pairs` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-llm_unavailable_pairs}

```python
llm_unavailable_pairs: int = 0
```

## `would_match` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-would_match}

```python
would_match: list[MatchDecision] = Field(default_factory=list)
```
