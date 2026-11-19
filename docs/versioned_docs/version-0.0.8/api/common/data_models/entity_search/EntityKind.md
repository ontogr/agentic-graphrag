---
title: agrag.common.data_models.entity_search.EntityKind
sidebar_label: EntityKind
---

# `agrag.common.data_models.entity_search.EntityKind` \{#agrag-common-data_models-entity_search-EntityKind}

Bases: <code>StrEnum</code>

Whether an entity hit has a visible passage that mentions it.

**Attributes:**

- [**SUPPORTED**](#agrag-common-data_models-entity_search-EntityKind-SUPPORTED) – At least one visible passage in scope mentions the entity.
- [**UNSUPPORTED**](#agrag-common-data_models-entity_search-EntityKind-UNSUPPORTED) – Passages in scope mention the entity, but none of them is
  current. The entity is not a verified fact in the current text.

## `SUPPORTED` \{#agrag-common-data_models-entity_search-EntityKind-SUPPORTED}

```python
SUPPORTED = 'supported'
```

## `UNSUPPORTED` \{#agrag-common-data_models-entity_search-EntityKind-UNSUPPORTED}

```python
UNSUPPORTED = 'unsupported'
```
