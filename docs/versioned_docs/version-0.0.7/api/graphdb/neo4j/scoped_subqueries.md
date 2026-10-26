---
title: agrag.graphdb.neo4j.scoped_subqueries
sidebar_label: scoped_subqueries
---

# `agrag.graphdb.neo4j.scoped_subqueries` \{#agrag-graphdb-neo4j-scoped_subqueries}

```python
scoped_subqueries(query:str) -> str
```

Rewrite importing `CALL { WITH x ... }` subqueries to the scoped form.

The shared builders write a subquery that imports its variables with a
leading `WITH`, the form every supported backend runs. Neo4j 5.23 and
later report that form as deprecated in favor of `CALL (x) { ... }`, so
this store sends the scoped form. Only a `WITH` that lists plain variable
names directly after `CALL {` is rewritten.

**Parameters:**

- **query** (<code>str</code>) – The Cypher text from a builder.

**Returns:**

- <code>str</code> – The query with each such subquery in scoped form.
