---
title: agrag.graphdb.serialize.parse_entity_node
sidebar_label: parse_entity_node
---

# `agrag.graphdb.serialize.parse_entity_node` \{#agrag-graphdb-serialize-parse_entity_node}

```python
parse_entity_node(node:object) -> Entity | None
```

Parse one stored entity's property dict into an Entity.

Neo4j rows carry no labels, so the label is the prefix of the node's
`merge_key`.

**Parameters:**

- **node** (<code>object</code>) – The node's properties, as a `RETURN n` row holds them.

**Returns:**

- <code>[Entity](../../common/data_models/entity/Entity-ref.md) | None</code> – The entity, or `None` when `node` is not a property dict or has no
- <code>[Entity](../../common/data_models/entity/Entity-ref.md) | None</code> – usable `id` or `merge_key`.
