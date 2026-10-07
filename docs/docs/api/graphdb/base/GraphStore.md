---
title: agrag.graphdb.base.GraphStore
sidebar_label: GraphStore
---

# `agrag.graphdb.base.GraphStore` \{#agrag-graphdb-base-GraphStore}

Bases: <code>ABC</code>

A graph database backend: schema, writes, and native vector search.

**Functions:**

- [**close**](#agrag-graphdb-base-GraphStore-close) – Release the backend connection.
- [**connect**](#agrag-graphdb-base-GraphStore-connect) – Open the backend connection and verify connectivity.
- [**ensure_vector_index**](#agrag-graphdb-base-GraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-base-GraphStore-execute_read) – Run a read transaction.
- [**execute_write**](#agrag-graphdb-base-GraphStore-execute_write) – Run a write transaction.
- [**register_labels**](#agrag-graphdb-base-GraphStore-register_labels) – Mark labels as known, without writing anything.
- [**register_relation_types**](#agrag-graphdb-base-GraphStore-register_relation_types) – Mark relationship types as known, without writing anything.
- [**session**](#agrag-graphdb-base-GraphStore-session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag-graphdb-base-GraphStore-setup_constraints) – Create per-label and per-relation-type uniqueness constraints.
- [**setup_indexes**](#agrag-graphdb-base-GraphStore-setup_indexes) – Create per-label property indexes.
- [**transaction**](#agrag-graphdb-base-GraphStore-transaction) – Start an explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag-graphdb-base-GraphStore-upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag-graphdb-base-GraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-base-GraphStore-vector_search) – Search nodes by dense vector.

## `close` \{#agrag-graphdb-base-GraphStore-close}

```python
close() -> None
```

Release the backend connection.

## `connect` \{#agrag-graphdb-base-GraphStore-connect}

```python
connect() -> None
```

Open the backend connection and verify connectivity.

## `ensure_vector_index` \{#agrag-graphdb-base-GraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>str</code>) – The node label to index.
- **vector_property** (<code>str</code>) – The embedding property name.
- **dimensions** (<code>int</code>) – The embedding dimension. If the index already exists
  with a different dimension, this raises.
- **distance** (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – The distance metric.

**Raises:**

- <code>EmbeddingDimensionMismatchError</code> – The index already exists with a
  different dimension than `dimensions`.

## `execute_read` \{#agrag-graphdb-base-GraphStore-execute_read}

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read transaction.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.
- **timeout** (<code>float | None</code>) – Server-side transaction timeout in seconds. The
  database terminates the transaction when it runs
  longer. None uses the server's default timeout.
  Backends that cannot enforce a timeout ignore it.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

## `execute_write` \{#agrag-graphdb-base-GraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

## `register_labels` \{#agrag-graphdb-base-GraphStore-register_labels}

```python
register_labels(labels:Sequence[str]) -> None
```

Mark labels as known, without writing anything.

setup_constraints()/setup_indexes() only cover labels this instance
has already written (or that already exist live in the database) —
both empty on a brand-new database. register_labels lets a caller
holding a GraphSchema (Graph.open()) provision a fresh database
fully before its first write.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>ValueError</code> – Any label is not a safe identifier.

## `register_relation_types` \{#agrag-graphdb-base-GraphStore-register_relation_types}

```python
register_relation_types(types:Sequence[str]) -> None
```

Mark relationship types as known, without writing anything.

The relationship-type counterpart to register_labels — see its
docstring for why this exists.

**Parameters:**

- **types** (<code>Sequence\[str\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>ValueError</code> – Any type is not a safe identifier.

## `session` \{#agrag-graphdb-base-GraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>AbstractAsyncContextManager\[Any\]</code> – A context manager yielding a backend session.

## `setup_constraints` \{#agrag-graphdb-base-GraphStore-setup_constraints}

```python
setup_constraints() -> None
```

Create per-label and per-relation-type uniqueness constraints.

Constraints cover every node label and relationship type written
through this instance or already present in the database, so a fresh
instance can set up an existing database without first rewriting
every record.

## `setup_indexes` \{#agrag-graphdb-base-GraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Create per-label property indexes.

Covers every node label written through this instance or already
present in the database, so a fresh instance can set up an existing
database without first rewriting every record.

## `transaction` \{#agrag-graphdb-base-GraphStore-transaction}

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Start an explicit transaction spanning multiple writes.

Every call through the yielded handle should join one backend
transaction, committing as a whole on clean exit from the
`async with` block and rolling back as a whole if the block raises.
The default here simply yields `self` and gives no atomicity beyond
what each individual call already provides; a backend that can offer
real atomicity, such as `Neo4jGraphStore`, overrides this with a
driver transaction.

Use this when a caller must guarantee several writes either all apply
or none do, such as `apply_merge`'s survivor upsert and alias claim.

**Returns:**

- <code>AsyncIterator\[[GraphStoreTransaction](GraphStoreTransaction.md)\]</code> – An async context manager yielding the transactional handle.

## `upsert_nodes` \{#agrag-graphdb-base-GraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

**Parameters:**

- **label** (<code>str</code>) – The label this batch is tracked under for constraint and
  index bookkeeping.
- **nodes** (<code>Sequence\[[NodeRecord](../../common/data_models/graph_record/NodeRecord.md)\]</code>) – The node records to upsert. Each node's `NodeRecord.labels`
  names the full label set actually written to it, which may
  include labels beyond `label`.
- **batch_size** (<code>int</code>) – Records per backend write call, applied within each
  distinct label set when `nodes` mixes more than one. Must
  be positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight Cutover Job's id. The store tags
  each node it creates, so retrieval skips it until the job
  commits. A node that already exists keeps its current pending
  state: a node tagged by another in-flight job stays tagged,
  and None does not commit it. None writes committed data.

**Returns:**

- <code>[UpsertResult](../../common/data_models/graph_record/UpsertResult.md)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

## `upsert_relations` \{#agrag-graphdb-base-GraphStore-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> UpsertResult
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>Sequence\[[RelationRecord](../../common/data_models/graph_record/RelationRecord.md)\]</code>) – The relation records to upsert.
- **batch_size** (<code>int</code>) – Records per backend write call. Must be positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight Cutover Job's id. The store tags
  each relationship it creates, so retrieval skips it until
  the job commits. A relationship that already exists keeps its
  current pending state: one tagged by another in-flight job
  stays tagged, and None does not commit it. None writes
  committed data.

**Returns:**

- <code>[UpsertResult](../../common/data_models/graph_record/UpsertResult.md)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

## `vector_search` \{#agrag-graphdb-base-GraphStore-vector_search}

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector.

**Parameters:**

- **label** (<code>str</code>) – The node label to search.
- **vector_property** (<code>str</code>) – The embedding property name.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – Maximum number of hits.
- **filters** (<code>dict\[str, Any\] | None</code>) – An optional flat-dict filter on node properties.

**Returns:**

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The matched hits, highest score first.
