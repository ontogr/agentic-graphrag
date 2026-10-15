---
title: agrag.common.data_models.entity_search
sidebar_label: entity_search
---

# `agrag.common.data_models.entity_search` \{#agrag-common-data_models-entity_search}

Models for entity discovery and bounded entity exploration.

An entity hit carries the passages that mention the entity, as evidence ids. An
exploration edge is either an assertion, with supporting passages, or a path,
which is a connection that no passage states. The models here are the values
that these calls exchange with callers.

**Classes:**

- [**EdgeKind**](EdgeKind.md) – Whether an exploration edge is supported by a passage.
- [**EntityHit**](EntityHit.md) – One entity found by entity discovery.
- [**EntityKind**](EntityKind.md) – Whether an entity hit has a visible passage that mentions it.
- [**EntityResult**](EntityResult.md) – The result of one entity discovery call.
- [**ExplorationBound**](ExplorationBound.md) – A bound that cut an exploration.
- [**ExplorationEdge**](ExplorationEdge.md) – One relation between two entities found by exploration.
- [**ExplorationNode**](ExplorationNode.md) – An entity reached by exploration.
- [**ExplorationResult**](ExplorationResult.md) – The result of one exploration call.
- [**ExplorationStatus**](ExplorationStatus.md) – The outcome of an exploration call.
- [**SupportingPassage**](SupportingPassage.md) – A visible passage that supports an entity or a relation.
