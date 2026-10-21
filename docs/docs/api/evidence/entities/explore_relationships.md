---
title: agrag.evidence.entities.explore_relationships
sidebar_label: explore_relationships
---

# `agrag.evidence.entities.explore_relationships` \{#agrag-evidence-entities-explore_relationships}

```python
explore_relationships(store:GraphStore, entity_id:str, *, scope:frozenset[str], relation_types:Sequence[str] | None = None, depth:int = 1, max_nodes:int = 25, max_edges:int = 50) -> ExplorationResult
```

Explore the entity relations around one entity, within bounds.

The walk follows relations that join two entities. With `relation_types`
only those types are followed. Without it, every schema relation type is
followed, and graph-owned types such as `HAS_PART` and `MENTIONED_IN` are
never followed. An entity can be reached only through a passage in scope, the
same rule as in `entity_search`.

A relation with a visible passage in scope is an assertion, and its passages
are listed in the edge. A relation without any passage is a path. A relation
whose passages are all superseded or out of scope is dropped.

The walk stops at the bound it hits first in each step, and `truncated_by`
names every bound that cut the walk. `depth` reports the bound when an
entity at the last depth has a connection to an entity that was not reached.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to read.
- **entity_id** (<code>str</code>) – The id of the start entity, as a canonical UUID string.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents whose passages may be used.
- **relation_types** (<code>Sequence\[str\] | None</code>) – The relation types to follow. None follows every schema
  relation type.
- **depth** (<code>int</code>) – How many relations to follow from the start entity. 1 or 2.
- **max_nodes** (<code>int</code>) – The most entities to return, not counting the start. Between 1
  and 200.
- **max_edges** (<code>int</code>) – The most edges to return. Between 1 and 200.

**Returns:**

- <code>[ExplorationResult](../../common/data_models/entity_search/ExplorationResult.md)</code> – The nodes, edges and bounds. An unavailable or malformed start gives no
- <code>[ExplorationResult](../../common/data_models/entity_search/ExplorationResult.md)</code> – nodes or edges.

**Raises:**

- <code>ValueError</code> – `depth`, `max_nodes` or `max_edges` is outside its range.
