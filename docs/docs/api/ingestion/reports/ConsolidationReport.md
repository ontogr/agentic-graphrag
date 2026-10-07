---
title: agrag.ingestion.reports.ConsolidationReport
sidebar_label: ConsolidationReport
---

# `agrag.ingestion.reports.ConsolidationReport` \{#agrag-ingestion-reports-ConsolidationReport}

Bases: <code>BaseModel</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_match**](#agrag-ingestion-reports-ConsolidationReport-would_match) (<code>list\[[MatchDecision](../resolved_entities/MatchDecision.md)\]</code>) – Confirmed non-exact matches found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-ConsolidationReport-applied) (<code>bool</code>) – Whether the matches were applied.
- [**failures**](#agrag-ingestion-reports-ConsolidationReport-failures) (<code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Failures reading the candidates of an entity, which that
  entity then skips, and failures writing a match graph or
  rebuilding resolved entities. Only the candidate read failures
  appear when apply is False.
- [**ambiguous_count**](#agrag-ingestion-reports-ConsolidationReport-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.

## `ambiguous_count` \{#agrag-ingestion-reports-ConsolidationReport-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `applied` \{#agrag-ingestion-reports-ConsolidationReport-applied}

```python
applied: bool = False
```

## `failures` \{#agrag-ingestion-reports-ConsolidationReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `would_match` \{#agrag-ingestion-reports-ConsolidationReport-would_match}

```python
would_match: list[MatchDecision] = Field(default_factory=list)
```
