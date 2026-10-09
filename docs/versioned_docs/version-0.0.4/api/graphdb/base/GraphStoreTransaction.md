---
title: agrag.graphdb.base.GraphStoreTransaction
sidebar_label: GraphStoreTransaction
---

# `agrag.graphdb.base.GraphStoreTransaction` \{#agrag-graphdb-base-GraphStoreTransaction}

Bases: <code>Protocol</code>

The read/write/upsert surface available inside a `transaction()` block.

A structural type, not a base class: `GraphStore` itself satisfies it
(the default `transaction()` yields `self`), and a backend's own
transaction handle, such as Neo4j's, satisfies it without inheriting from
anything here.

**Functions:**

- [**execute_read**](#agrag-graphdb-base-GraphStoreTransaction-execute_read) – Run a read inside the surrounding transaction.
- [**execute_write**](#agrag-graphdb-base-GraphStoreTransaction-execute_write) – Run a write inside the surrounding transaction.
- [**upsert_nodes**](#agrag-graphdb-base-GraphStoreTransaction-upsert_nodes) – Write or merge nodes inside the surrounding transaction.
- [**upsert_relations**](#agrag-graphdb-base-GraphStoreTransaction-upsert_relations) – Write or merge relationships inside the surrounding transaction.

## `execute_read` \{#agrag-graphdb-base-GraphStoreTransaction-execute_read}

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read inside the surrounding transaction.

## `execute_write` \{#agrag-graphdb-base-GraphStoreTransaction-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write inside the surrounding transaction.

## `upsert_nodes` \{#agrag-graphdb-base-GraphStoreTransaction-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult | None
```

Write or merge nodes inside the surrounding transaction.

## `upsert_relations` \{#agrag-graphdb-base-GraphStoreTransaction-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult | None
```

Write or merge relationships inside the surrounding transaction.
