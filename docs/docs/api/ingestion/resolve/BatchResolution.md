---
title: agrag.ingestion.resolve.BatchResolution
sidebar_label: BatchResolution
---

# `agrag.ingestion.resolve.BatchResolution` \{#agrag-ingestion-resolve-BatchResolution}

```python
BatchResolution(exact_matches:dict[int, Entity], groups:list[ResolutionGroup], result:ResolutionResult | None, persisted_ids:dict[int, UUID] = dict(), candidate_entities:dict[UUID, Entity] = dict(), failures:list[StageFailure] = list(), unresolved_indices:set[int] = set()) -> None
```

The outcome of resolving one batch of mentions.

**Attributes:**

- [**exact_matches**](#agrag-ingestion-resolve-BatchResolution-exact_matches) (<code>dict\[int, [Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – Mention index to the persisted entity it matches by
  merge key.
- [**groups**](#agrag-ingestion-resolve-BatchResolution-groups) (<code>list\[[ResolutionGroup](resolver/ResolutionGroup.md)\]</code>) – Mentions that share one raw entity identity.
- [**result**](#agrag-ingestion-resolve-BatchResolution-result) (<code>[ResolutionResult](resolver/ResolutionResult.md) | None</code>) – The semantic resolver pass over the mentions and their
  persisted candidates. `None` when the batch has no mentions.
- [**persisted_ids**](#agrag-ingestion-resolve-BatchResolution-persisted_ids) (<code>dict\[int, UUID\]</code>) – Index of each synthetic candidate mention to the id of
  the persisted entity it stands for.
- [**candidate_entities**](#agrag-ingestion-resolve-BatchResolution-candidate_entities) (<code>dict\[UUID, [Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – Persisted candidates by id.
- [**failures**](#agrag-ingestion-resolve-BatchResolution-failures) (<code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code>) – One StageFailure per mention whose candidate read failed.
- [**unresolved_indices**](#agrag-ingestion-resolve-BatchResolution-unresolved_indices) (<code>set\[int\]</code>) – Indices of the mentions in `failures`. A
  mention whose read failed neither starts nor joins a comparison.

## `candidate_entities` \{#agrag-ingestion-resolve-BatchResolution-candidate_entities}

```python
candidate_entities: dict[UUID, Entity] = field(default_factory=dict)
```

## `exact_matches` \{#agrag-ingestion-resolve-BatchResolution-exact_matches}

```python
exact_matches: dict[int, Entity]
```

## `failures` \{#agrag-ingestion-resolve-BatchResolution-failures}

```python
failures: list[StageFailure] = field(default_factory=list)
```

## `groups` \{#agrag-ingestion-resolve-BatchResolution-groups}

```python
groups: list[ResolutionGroup]
```

## `persisted_ids` \{#agrag-ingestion-resolve-BatchResolution-persisted_ids}

```python
persisted_ids: dict[int, UUID] = field(default_factory=dict)
```

## `result` \{#agrag-ingestion-resolve-BatchResolution-result}

```python
result: ResolutionResult | None
```

## `unresolved_indices` \{#agrag-ingestion-resolve-BatchResolution-unresolved_indices}

```python
unresolved_indices: set[int] = field(default_factory=set)
```
