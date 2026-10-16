---
title: agrag.ingestion.resolve.candidate_source.GraphCandidateSource
sidebar_label: GraphCandidateSource
---

# `agrag.ingestion.resolve.candidate_source.GraphCandidateSource` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource}

```python
GraphCandidateSource(*, graph_store:GraphStore, embedder:Embedder, entity_labels:Sequence[str] = (), top_k:int = 50) -> None
```

Bases: <code>[CandidateSource](CandidateSource.md)</code>

Block by label in-batch. Search persisted entities globally with ANN.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-candidates_for) – Return every other mention sharing the indexed mention's label.
- [**global_candidates_for**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-global_candidates_for) – Return persisted entities found by the native vector search.

**Attributes:**

- [**embedder**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-embedder) –
- [**entity_labels**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-entity_labels) –
- [**graph_store**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-graph_store) –
- [**top_k**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-top_k) –

## `candidates_for` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return every other mention sharing the indexed mention's label.

## `embedder` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-embedder}

```python
embedder = embedder
```

## `entity_labels` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-entity_labels}

```python
entity_labels = tuple(entity_labels)
```

## `global_candidates_for` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-global_candidates_for}

```python
global_candidates_for(mention:ExtractedEntity) -> list[tuple[Entity, float]]
```

Return persisted entities found by the native vector search.

Each candidate is paired with the cosine similarity of the
`VectorHit` it came from. The association is keyed by hit id, never
by position: either branch can drop an entity (malformed payload,
label mismatch, failed load) without dropping the corresponding
score, so zipping the two lists positionally would silently shift
scores onto the wrong entities.

**Returns:**

- <code>list\[tuple\[[Entity](../../../common/data_models/entity/Entity-ref.md), float\]\]</code> – `(Entity, score)` pairs in hit order. `score` is `0.0` for
- <code>list\[tuple\[[Entity](../../../common/data_models/entity/Entity-ref.md), float\]\]</code> – an entity whose id is absent from the hit map, which should not
- <code>list\[tuple\[[Entity](../../../common/data_models/entity/Entity-ref.md), float\]\]</code> – happen since candidate ids come from those same hits.

**Raises:**

- <code>Exception</code> – The embedding, the vector search, or the graph read
  failed. An empty list means the search ran and found no
  candidate.

## `graph_store` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-graph_store}

```python
graph_store = graph_store
```

## `top_k` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-top_k}

```python
top_k = top_k
```
