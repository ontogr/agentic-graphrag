---
title: agrag.evidence.entities
sidebar_label: entities
---

# `agrag.evidence.entities` \{#agrag-evidence-entities}

Find entities by name or meaning, and explore typed relations around one entity.

An entity is returned only with the passages that mention it, and only when at
least one of those passages is in the caller's scope. Each passage is an evidence
id. An entity whose passages are all superseded is returned as unsupported, with
no passages. Exploration follows entity-to-entity relations with bounded depth,
size and edge count. A relation with a visible passage is an assertion, and a
connection with no passage is a path.

**Functions:**

- [**entity_search**](entity_search.md) – Find up to `limit` entities that match a query by name or by meaning.
- [**explore_relationships**](explore_relationships.md) – Explore the entity relations around one entity, within bounds.
