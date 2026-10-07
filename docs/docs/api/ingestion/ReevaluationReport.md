---
title: agrag.ingestion.ReevaluationReport
sidebar_label: ReevaluationReport
---

# `agrag.ingestion.ReevaluationReport` \{#agrag-ingestion-ReevaluationReport}

Bases: <code>BaseModel</code>

Report from Graph.reevaluate().

**Attributes:**

- [**entities_reevaluated**](#agrag-ingestion-ReevaluationReport-entities_reevaluated) (<code>list\[UUID\]</code>) – Input entity ids reevaluated, deduped with
  input order preserved.
- [**matches_added**](#agrag-ingestion-ReevaluationReport-matches_added) (<code>list\[[MatchDecision](resolved_entities/MatchDecision.md)\]</code>) – Confirmed matches with no active edge, now written.
- [**matches_removed**](#agrag-ingestion-ReevaluationReport-matches_removed) (<code>list\[UUID\]</code>) – Ids of active match edges the resolver did not
  confirm, now deactivated.
- [**unchanged_count**](#agrag-ingestion-ReevaluationReport-unchanged_count) (<code>int</code>) – Input entities with no incident added or removed
  edge.

## `entities_reevaluated` \{#agrag-ingestion-ReevaluationReport-entities_reevaluated}

```python
entities_reevaluated: list[UUID] = Field(default_factory=list)
```

## `matches_added` \{#agrag-ingestion-ReevaluationReport-matches_added}

```python
matches_added: list[MatchDecision] = Field(default_factory=list)
```

## `matches_removed` \{#agrag-ingestion-ReevaluationReport-matches_removed}

```python
matches_removed: list[UUID] = Field(default_factory=list)
```

## `unchanged_count` \{#agrag-ingestion-ReevaluationReport-unchanged_count}

```python
unchanged_count: int = 0
```
