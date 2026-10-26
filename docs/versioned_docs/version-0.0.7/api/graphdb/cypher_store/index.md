---
title: agrag.graphdb.cypher_store
sidebar_label: cypher_store
---

# `agrag.graphdb.cypher_store` \{#agrag-graphdb-cypher_store}

Write and bookkeeping logic shared by graph stores that speak Cypher.

**Classes:**

- [**CypherGraphStore**](CypherGraphStore.md) – A `GraphStore` for databases that run the shared Cypher builders.

**Functions:**

- [**query_parameter_attributes**](query_parameter_attributes.md) – Build `db.query.parameter.<key>` span attributes.
- [**require_deferred**](require_deferred.md) – Reject a job write that has nowhere to put deferred writes.
