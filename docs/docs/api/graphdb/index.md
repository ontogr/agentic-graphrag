---
title: agrag.graphdb
sidebar_position: 7
---


# `agrag.graphdb` \{#agrag-graphdb}

Graph storage backends and the build shortcut.

**Modules:**

- [**base**](base/index.md) – The GraphStore abstraction and its build shortcut helpers.
- [**entities**](entities/index.md) – Load persisted entities by id.
- [**errors**](errors/index.md) – Errors that the graph-store layer raises.
- [**neo4j**](neo4j/index.md) – Neo4j graph-store backend.
- [**serialize**](serialize/index.md) – Convert graph records to driver parameters and graph node rows to models.
- [**settings**](settings/index.md) – Settings for the Neo4j graph-store backend.

**Classes:**

- [**GraphStore**](GraphStore.md) – A graph database backend: schema, writes, and native vector search.
- [**GraphStoreError**](GraphStoreError.md) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](GraphStoreMissingExtraError.md) – A graph store exists, but its package extra is not installed.
- [**Neo4jGraphStore**](Neo4jGraphStore.md) – A `GraphStore` backed by Neo4j, using native vector indexes.
- [**Neo4jSettings**](Neo4jSettings.md) – Neo4j connection configuration.

**Functions:**

- [**build_graph_store**](build_graph_store.md) – Build a graph store from a backend name, or return one unchanged.

**Attributes:**

- [**GraphStoreName**](GraphStoreName.md) –
