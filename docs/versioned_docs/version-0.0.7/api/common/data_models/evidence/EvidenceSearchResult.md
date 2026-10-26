---
title: agrag.common.data_models.evidence.EvidenceSearchResult
sidebar_label: EvidenceSearchResult
---

# `agrag.common.data_models.evidence.EvidenceSearchResult` \{#agrag-common-data_models-evidence-EvidenceSearchResult}

Bases: <code>BaseModel</code>

The result of one search call.

**Attributes:**

- [**status**](#agrag-common-data_models-evidence-EvidenceSearchResult-status) (<code>[EvidenceSearchStatus](EvidenceSearchStatus.md)</code>) – The overall outcome. A failed leg never shows as NO_MATCH.
- [**hits**](#agrag-common-data_models-evidence-EvidenceSearchResult-hits) (<code>list\[[EvidenceSearchHit](EvidenceSearchHit.md)\]</code>) – The visible passages, best first. Empty unless status is OK or
  PARTIAL.
- [**truncated**](#agrag-common-data_models-evidence-EvidenceSearchResult-truncated) (<code>bool</code>) – True when the search reached its candidate ceiling before it
  found `limit` visible passages, so more passages may exist.
- [**index_state**](#agrag-common-data_models-evidence-EvidenceSearchResult-index_state) (<code>[IndexState](IndexState.md) | None</code>) – Whether the needed indexes were ready. None when no index
  was checked, which happens for an empty scope.
- [**failures**](#agrag-common-data_models-evidence-EvidenceSearchResult-failures) (<code>list\[[LegFailure](LegFailure.md)\]</code>) – Failed legs, and a failed rerank stage. A failed rerank does
  not change the status.
- [**reranked**](#agrag-common-data_models-evidence-EvidenceSearchResult-reranked) (<code>bool</code>) – True when a reranker reordered the hits. Each hit's score is
  then the cross-encoder score, whose scale differs from the fused
  score.

## `failures` \{#agrag-common-data_models-evidence-EvidenceSearchResult-failures}

```python
failures: list[LegFailure] = Field(default_factory=list)
```

## `hits` \{#agrag-common-data_models-evidence-EvidenceSearchResult-hits}

```python
hits: list[EvidenceSearchHit] = Field(default_factory=list)
```

## `index_state` \{#agrag-common-data_models-evidence-EvidenceSearchResult-index_state}

```python
index_state: IndexState | None = None
```

## `reranked` \{#agrag-common-data_models-evidence-EvidenceSearchResult-reranked}

```python
reranked: bool = False
```

## `status` \{#agrag-common-data_models-evidence-EvidenceSearchResult-status}

```python
status: EvidenceSearchStatus
```

## `truncated` \{#agrag-common-data_models-evidence-EvidenceSearchResult-truncated}

```python
truncated: bool = False
```
