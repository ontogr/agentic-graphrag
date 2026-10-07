---
title: agrag.ingestion.resolve.ResolutionGroup
sidebar_label: ResolutionGroup
---

# `agrag.ingestion.resolve.ResolutionGroup` \{#agrag-ingestion-resolve-ResolutionGroup}

Bases: <code>BaseModel</code>

One set of ExtractedEntity indices resolution decided are the same entity.

**Attributes:**

- [**entity_indices**](#agrag-ingestion-resolve-ResolutionGroup-entity_indices) (<code>list\[int\]</code>) – Indices into the entity list passed to Resolver.resolve.
  A group of one means resolution found no match for that entity.

## `entity_indices` \{#agrag-ingestion-resolve-ResolutionGroup-entity_indices}

```python
entity_indices: list[int]
```
