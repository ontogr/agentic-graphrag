---
title: agrag.ingestion.resolved_entities.MatchDecision
sidebar_label: MatchDecision
---

# `agrag.ingestion.resolved_entities.MatchDecision` \{#agrag-ingestion-resolved_entities-MatchDecision}

Bases: <code>BaseModel</code>

A confirmed non-exact entity match ready to persist.

**Attributes:**

- [**entity_a_id**](#agrag-ingestion-resolved_entities-MatchDecision-entity_a_id) (<code>UUID</code>) – Id of the first matched entity.
- [**entity_b_id**](#agrag-ingestion-resolved_entities-MatchDecision-entity_b_id) (<code>UUID</code>) – Id of the second matched entity.
- [**comparator**](#agrag-ingestion-resolved_entities-MatchDecision-comparator) (<code>str</code>) – Name of the comparator that confirmed the match.
- [**score**](#agrag-ingestion-resolved_entities-MatchDecision-score) (<code>float | None</code>) – Comparator score, if available.
- [**reasoning**](#agrag-ingestion-resolved_entities-MatchDecision-reasoning) (<code>str | None</code>) – Comparator reasoning, if available.
- [**decided_at**](#agrag-ingestion-resolved_entities-MatchDecision-decided_at) (<code>datetime</code>) – Time when the match was confirmed.
- [**similarity**](#agrag-ingestion-resolved_entities-MatchDecision-similarity) (<code>float | None</code>) – Candidate similarity, if available.
- [**batch_id**](#agrag-ingestion-resolved_entities-MatchDecision-batch_id) (<code>UUID | None</code>) – Resolution batch id, if available.

## `batch_id` \{#agrag-ingestion-resolved_entities-MatchDecision-batch_id}

```python
batch_id: UUID | None = None
```

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

## `similarity` \{#agrag-ingestion-resolved_entities-MatchDecision-similarity}

```python
similarity: float | None = None
```
