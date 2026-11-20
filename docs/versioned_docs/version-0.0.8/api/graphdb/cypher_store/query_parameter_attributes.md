---
title: agrag.graphdb.cypher_store.query_parameter_attributes
sidebar_label: query_parameter_attributes
---

# `agrag.graphdb.cypher_store.query_parameter_attributes` \{#agrag-graphdb-cypher_store-query_parameter_attributes}

```python
query_parameter_attributes(parameters:Mapping[str, Any] | None) -> dict[str, str]
```

Build `db.query.parameter.<key>` span attributes.

Skips vector-valued parameters, skips the untraced user-text parameters, and
strips vector-valued fields from nested dictionaries (including nested record
dicts) before serializing each value to a string.
