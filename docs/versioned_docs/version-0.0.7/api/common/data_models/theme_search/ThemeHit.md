---
title: agrag.common.data_models.theme_search.ThemeHit
sidebar_label: ThemeHit
---

# `agrag.common.data_models.theme_search.ThemeHit` \{#agrag-common-data_models-theme_search-ThemeHit}

Bases: <code>BaseModel</code>

One theme found by theme search.

**Attributes:**

- [**theme_id**](#agrag-common-data_models-theme_search-ThemeHit-theme_id) (<code>str</code>) – The id of the community node.
- [**score**](#agrag-common-data_models-theme_search-ThemeHit-score) (<code>float</code>) – The vector similarity of the query to the community report
  embedding. An ordering value. Higher scores rank first. It is not a
  confidence, and it is not a probability that the theme is relevant.
- [**entities**](#agrag-common-data_models-theme_search-ThemeHit-entities) (<code>list\[str\]</code>) – Up to five names of member entities that a visible in-scope
  passage mentions.
- [**passages**](#agrag-common-data_models-theme_search-ThemeHit-passages) (<code>list\[[SupportingPassage](../entity_search/SupportingPassage.md)\]</code>) – Visible in-scope passages that mention member entities, best
  first. Each passage is an evidence id. Fetch it to read the text.

## `entities` \{#agrag-common-data_models-theme_search-ThemeHit-entities}

```python
entities: list[str] = Field(default_factory=list)
```

## `passages` \{#agrag-common-data_models-theme_search-ThemeHit-passages}

```python
passages: list[SupportingPassage] = Field(default_factory=list)
```

## `score` \{#agrag-common-data_models-theme_search-ThemeHit-score}

```python
score: float
```

## `theme_id` \{#agrag-common-data_models-theme_search-ThemeHit-theme_id}

```python
theme_id: str
```
