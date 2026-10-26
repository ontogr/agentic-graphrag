---
title: agrag.common.data_models.entity_search.EntityHit
sidebar_label: EntityHit
---

# `agrag.common.data_models.entity_search.EntityHit` \{#agrag-common-data_models-entity_search-EntityHit}

Bases: <code>BaseModel</code>

One entity found by entity search.

**Attributes:**

- [**entity_id**](#agrag-common-data_models-entity_search-EntityHit-entity_id) (<code>str</code>) – The id of the entity node.
- [**label**](#agrag-common-data_models-entity_search-EntityHit-label) (<code>str</code>) – The entity label the node was found under.
- [**name**](#agrag-common-data_models-entity_search-EntityHit-name) (<code>str</code>) – The entity name.
- [**properties**](#agrag-common-data_models-entity_search-EntityHit-properties) (<code>dict\[str, Any\]</code>) – The schema properties of the entity. Internal fields, the
  embedding and the source chunk list are left out.
- [**kind**](#agrag-common-data_models-entity_search-EntityHit-kind) (<code>[EntityKind](EntityKind.md)</code>) – Whether the entity has a visible supporting passage.
- [**score**](#agrag-common-data_models-entity_search-EntityHit-score) (<code>float</code>) – An ordering value. Higher scores rank first. It is not a
  confidence, and it is not a probability that the entity is correct.
- [**legs**](#agrag-common-data_models-entity_search-EntityHit-legs) (<code>list\[[EvidenceSearchLeg](../evidence/EvidenceSearchLeg.md)\]</code>) – The search legs that found the entity.
- [**support**](#agrag-common-data_models-entity_search-EntityHit-support) (<code>list\[[SupportingPassage](SupportingPassage.md)\]</code>) – Visible passages that mention the entity, up to the support
  limit of the call. Empty for an unsupported entity.

## `entity_id` \{#agrag-common-data_models-entity_search-EntityHit-entity_id}

```python
entity_id: str
```

## `kind` \{#agrag-common-data_models-entity_search-EntityHit-kind}

```python
kind: EntityKind
```

## `label` \{#agrag-common-data_models-entity_search-EntityHit-label}

```python
label: str
```

## `legs` \{#agrag-common-data_models-entity_search-EntityHit-legs}

```python
legs: list[EvidenceSearchLeg]
```

## `name` \{#agrag-common-data_models-entity_search-EntityHit-name}

```python
name: str
```

## `properties` \{#agrag-common-data_models-entity_search-EntityHit-properties}

```python
properties: dict[str, Any] = Field(default_factory=dict)
```

## `score` \{#agrag-common-data_models-entity_search-EntityHit-score}

```python
score: float
```

## `support` \{#agrag-common-data_models-entity_search-EntityHit-support}

```python
support: list[SupportingPassage] = Field(default_factory=list)
```
