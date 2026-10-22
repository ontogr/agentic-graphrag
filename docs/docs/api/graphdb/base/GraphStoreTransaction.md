---
title: agrag.graphdb.base.GraphStoreTransaction
sidebar_label: GraphStoreTransaction
---

# `agrag.graphdb.base.GraphStoreTransaction` \{#agrag-graphdb-base-GraphStoreTransaction}

Bases: <code>Protocol</code>

The read/write/upsert surface available inside transactional work.

A structural type, not a base class: `GraphStore` itself satisfies it
(the default `run_in_transaction()` passes `self`), and a backend's own
transaction handle, such as Neo4j's, satisfies it without inheriting from
anything here.

**Functions:**

- [**execute_read**](#agrag-graphdb-base-GraphStoreTransaction-execute_read) – Run a read inside the surrounding transaction.
- [**execute_write**](#agrag-graphdb-base-GraphStoreTransaction-execute_write) – Run a write inside the surrounding transaction.
- [**fulltext_copy_set**](#agrag-graphdb-base-GraphStoreTransaction-fulltext_copy_set) – Return `SET` clauses a backend needs to keep written text searchable.
- [**upsert_nodes**](#agrag-graphdb-base-GraphStoreTransaction-upsert_nodes) – Write or merge nodes inside the surrounding transaction.
- [**upsert_relations**](#agrag-graphdb-base-GraphStoreTransaction-upsert_relations) – Write or merge relationships inside the surrounding transaction.
- [**vector_value**](#agrag-graphdb-base-GraphStoreTransaction-vector_value) – Wrap a Cypher expression that holds an embedding for a property write.

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

## `fulltext_copy_set` \{#agrag-graphdb-base-GraphStoreTransaction-fulltext_copy_set}

```python
fulltext_copy_set(alias:str, source:str, properties:Iterable[str]) -> str
```

Return `SET` clauses a backend needs to keep written text searchable.

**Returns:**

- <code>str</code> – Clauses to add to the write, or an empty string when the backend
- <code>str</code> – searches the stored text directly.

## `upsert_nodes` \{#agrag-graphdb-base-GraphStoreTransaction-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None, deferred:DeferredWrites | None = None) -> UpsertResult | None
```

Write or merge nodes inside the surrounding transaction.

`pending_job_id` tags the rows the call creates. A write that reaches
a row the job did not create is not applied and is added to `deferred`,
which is required when `pending_job_id` is set.

**Raises:**

- <code>GraphStoreWriteConflictError</code> – `deferred` is None and a row is
  owned by another in-flight job. The transaction rolls back.

## `upsert_relations` \{#agrag-graphdb-base-GraphStoreTransaction-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None, deferred:DeferredWrites | None = None) -> UpsertResult | None
```

Write or merge relationships inside the surrounding transaction.

`pending_job_id` tags the rows the call creates. A write that reaches
a row the job did not create is not applied and is added to `deferred`,
which is required when `pending_job_id` is set.

**Raises:**

- <code>GraphStoreWriteConflictError</code> – `deferred` is None and a
  relationship is owned by another in-flight job. The
  transaction rolls back.

## `vector_value` \{#agrag-graphdb-base-GraphStoreTransaction-vector_value}

```python
vector_value(expression:str) -> str
```

Wrap a Cypher expression that holds an embedding for a property write.

**Returns:**

- <code>str</code> – The expression to assign to a vector property. Backends that store
- <code>str</code> – a plain float list return `expression` unchanged.
