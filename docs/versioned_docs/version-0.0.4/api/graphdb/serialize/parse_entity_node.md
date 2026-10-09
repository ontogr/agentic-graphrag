---
title: agrag.graphdb.serialize.parse_entity_node
sidebar_label: parse_entity_node
---

# `agrag.graphdb.serialize.parse_entity_node` \{#agrag-graphdb-serialize-parse_entity_node}

```python
parse_entity_node(node:object) -> Entity | None
```

Parse a GraphStore node row into an Entity.

Handles both neo4j Node objects and plain dict mocks used in unit tests.
