---
title: agrag.ingestion.reports.reevaluation_report.ReevaluationReport
sidebar_label: ReevaluationReport
---

# `agrag.ingestion.reports.reevaluation_report.ReevaluationReport` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport}

Bases: <code>BaseModel</code>

Report from Graph.reevaluate().

**Attributes:**

- [**entities_reevaluated**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-entities_reevaluated) (<code>list\[UUID\]</code>) – Input entity ids reevaluated, deduped with
  input order preserved.
- [**matches_added**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_added) (<code>list\[[MatchDecision](../../resolved_entities/MatchDecision.md)\]</code>) – Confirmed matches with no active edge, now written.
- [**matches_removed**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_removed) (<code>list\[UUID\]</code>) – Ids of active match edges the resolver rejected, now
  deactivated. A rejection is an embedding score under the discard
  threshold or an explicit LLM "no match".
- [**matches_unverified**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_unverified) (<code>list\[UUID\]</code>) – Ids of active match edges the resolver could not
  re-check, left active. The LLM request failed, the pair was over
  the per-label cap, no LLM settings were found, or the model
  answered uncertain.
- [**failed_llm_requests**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-failed_llm_requests) (<code>int</code>) – LLM verification requests that raised.
- [**cap_truncated_pairs**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-cap_truncated_pairs) (<code>int</code>) – Ambiguous pairs over the per-label cap.
- [**llm_unavailable_pairs**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-llm_unavailable_pairs) (<code>int</code>) – Ambiguous pairs that never reached the LLM
  because no LLM settings were found.
- [**unchanged_count**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-unchanged_count) (<code>int</code>) – Input entities with no incident added or removed
  edge.

## `cap_truncated_pairs` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

## `entities_reevaluated` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-entities_reevaluated}

```python
entities_reevaluated: list[UUID] = Field(default_factory=list)
```

## `failed_llm_requests` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `llm_unavailable_pairs` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-llm_unavailable_pairs}

```python
llm_unavailable_pairs: int = 0
```

## `matches_added` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_added}

```python
matches_added: list[MatchDecision] = Field(default_factory=list)
```

## `matches_removed` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_removed}

```python
matches_removed: list[UUID] = Field(default_factory=list)
```

## `matches_unverified` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_unverified}

```python
matches_unverified: list[UUID] = Field(default_factory=list)
```

## `unchanged_count` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-unchanged_count}

```python
unchanged_count: int = 0
```
