---
title: agrag.ingestion.resolved_entities.MatchDecision
sidebar_label: MatchDecision
---

# `agrag.ingestion.resolved_entities.MatchDecision` \{#agrag-ingestion-resolved_entities-MatchDecision}

Bases: <code>BaseModel</code>

A confirmed non-exact entity match ready to persist.

**Attributes:**

- [**comparator**](#agrag-ingestion-resolved_entities-MatchDecision-comparator) (<code>str</code>) –
- [**decided_at**](#agrag-ingestion-resolved_entities-MatchDecision-decided_at) (<code>datetime</code>) –
- [**entity_a_id**](#agrag-ingestion-resolved_entities-MatchDecision-entity_a_id) (<code>UUID</code>) –
- [**entity_b_id**](#agrag-ingestion-resolved_entities-MatchDecision-entity_b_id) (<code>UUID</code>) –
- [**reasoning**](#agrag-ingestion-resolved_entities-MatchDecision-reasoning) (<code>str | None</code>) –
- [**score**](#agrag-ingestion-resolved_entities-MatchDecision-score) (<code>float | None</code>) –

## `comparator` \{#agrag-ingestion-resolved_entities-MatchDecision-comparator}

```python
comparator: str
```

## `decided_at` \{#agrag-ingestion-resolved_entities-MatchDecision-decided_at}

```python
decided_at: datetime
```

## `entity_a_id` \{#agrag-ingestion-resolved_entities-MatchDecision-entity_a_id}

```python
entity_a_id: UUID
```

## `entity_b_id` \{#agrag-ingestion-resolved_entities-MatchDecision-entity_b_id}

```python
entity_b_id: UUID
```

## `reasoning` \{#agrag-ingestion-resolved_entities-MatchDecision-reasoning}

```python
reasoning: str | None = None
```

## `score` \{#agrag-ingestion-resolved_entities-MatchDecision-score}

```python
score: float | None = None
```
