---
title: agrag.graphdb.neo4j.Neo4jGraphStore
sidebar_label: Neo4jGraphStore
---

# `agrag.graphdb.neo4j.Neo4jGraphStore` \{#agrag-graphdb-neo4j-Neo4jGraphStore}

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[GraphStore](../base/GraphStore.md)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop.

**Functions:**

- [**blocked_candidate_keys**](#agrag-graphdb-neo4j-Neo4jGraphStore-blocked_candidate_keys) – Return keys with a committed candidate that is not pending.
- [**close**](#agrag-graphdb-neo4j-Neo4jGraphStore-close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag-graphdb-neo4j-Neo4jGraphStore-connect) – Open the driver and verify connectivity.
- [**ensure_relation_constraint**](#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_relation_constraint) – Create a relationship type's `id` uniqueness constraint once.
- [**ensure_vector_index**](#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-neo4j-Neo4jGraphStore-execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag-graphdb-neo4j-Neo4jGraphStore-execute_write) – Run a write transaction and return its rows.
- [**register_labels**](#agrag-graphdb-neo4j-Neo4jGraphStore-register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag-graphdb-neo4j-Neo4jGraphStore-register_relation_types) – Add types to this instance's known-relation-type set.
- [**run_in_transaction**](#agrag-graphdb-neo4j-Neo4jGraphStore-run_in_transaction) – Run work in a Neo4j managed transaction and return its result.
- [**session**](#agrag-graphdb-neo4j-Neo4jGraphStore-session) – Open a session to the configured database.
- [**setup_constraints**](#agrag-graphdb-neo4j-Neo4jGraphStore-setup_constraints) – Create `id` and `merge_key` uniqueness constraints per label.
- [**setup_indexes**](#agrag-graphdb-neo4j-Neo4jGraphStore-setup_indexes) – Set up indexes now provided by the store's uniqueness constraints.
- [**upsert_candidates**](#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_candidates) – Write candidates without changing nodes that already exist.
- [**upsert_nodes**](#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-neo4j-Neo4jGraphStore-vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](../settings/Neo4jSettings.md) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>AsyncDriver | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this store's methods produce.

## `blocked_candidate_keys` \{#agrag-graphdb-neo4j-Neo4jGraphStore-blocked_candidate_keys}

```python
blocked_candidate_keys(keys:Sequence[str]) -> set[str]
```

Return keys with a committed candidate that is not pending.

## `close` \{#agrag-graphdb-neo4j-Neo4jGraphStore-close}

```python
close() -> None
```

Close the driver, releasing its connection pool.

## `connect` \{#agrag-graphdb-neo4j-Neo4jGraphStore-connect}

```python
connect() -> None
```

Open the driver and verify connectivity.

## `ensure_relation_constraint` \{#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_relation_constraint}

```python
ensure_relation_constraint(rel_type:str) -> None
```

Create a relationship type's `id` uniqueness constraint once.

Public entry point onto `_ensure_relation_constraint` for
`_Neo4jTransaction.upsert_relations`, which must give the same
constraint-before-first-write guarantee inside an explicit
transaction that the non-transactional `upsert_relations` gives.

**Parameters:**

- **rel_type** (<code>str</code>) – The relationship type to ensure a constraint for. Must
  already be validated.

## `ensure_vector_index` \{#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

A concurrent creator can commit the same index after this operation
starts. Neo4j reports that race as an equivalent-schema error, which
means the requested index already exists.

**Raises:**

- <code>[EmbeddingDimensionMismatchError](../../embedding/errors/EmbeddingDimensionMismatchError.md)</code> – The index already exists with a
  different dimension than `dimensions`.

## `execute_read` \{#agrag-graphdb-neo4j-Neo4jGraphStore-execute_read}

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read transaction and return its rows.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.
- **timeout** (<code>float | None</code>) – Server-side transaction timeout in seconds,
  applied through the driver's `unit_of_work` so the
  database terminates the transaction when it runs
  longer. None uses the server's default timeout.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

## `execute_write` \{#agrag-graphdb-neo4j-Neo4jGraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

**Raises:**

- <code>[GraphStoreConstraintViolationError](../errors/GraphStoreConstraintViolationError.md)</code> – The write violated a uniqueness
  constraint, translated from the driver's own exception so
  callers do not need a hard dependency on it.

## `register_labels` \{#agrag-graphdb-neo4j-Neo4jGraphStore-register_labels}

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>ValueError</code> – Any label is not a safe identifier.

## `register_relation_types` \{#agrag-graphdb-neo4j-Neo4jGraphStore-register_relation_types}

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>Sequence\[str\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>ValueError</code> – Any type is not a safe identifier.

## `run_in_transaction` \{#agrag-graphdb-neo4j-Neo4jGraphStore-run_in_transaction}

```python
run_in_transaction(work:Callable[[GraphStoreTransaction], Awaitable[_T]]) -> _T
```

Run work in a Neo4j managed transaction and return its result.

Neo4j may retry `work` after a transient failure. The callback must
therefore be safe to run again and must return results rather than
mutate state outside the callback.

**Parameters:**

- **work** (<code>Callable\[\[[GraphStoreTransaction](../base/GraphStoreTransaction.md)\], Awaitable\[\_T\]\]</code>) – The reads and writes to run together. Must be safe to retry.

**Returns:**

- <code>\_T</code> – Whatever `work` returns.

**Raises:**

- <code>[GraphStoreConstraintViolationError](../errors/GraphStoreConstraintViolationError.md)</code> – The transaction violated a
  uniqueness constraint.

## `session` \{#agrag-graphdb-neo4j-Neo4jGraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

## `setup_constraints` \{#agrag-graphdb-neo4j-Neo4jGraphStore-setup_constraints}

```python
setup_constraints() -> None
```

Create `id` and `merge_key` uniqueness constraints per label.

"Known" means written by this instance or already present in the
database, so a fresh store can set up constraints for an existing
database without first rewriting every record. The `id` constraint
backs node identity; `merge_key` prevents concurrent ingestion from
creating duplicate canonical entities. Also creates the global
uniqueness constraint on `NODE_IDENTITY_LABEL` that
`upsert_node_query`'s `MERGE` relies on to resolve a node by id
regardless of its other, mutable labels, and a per-type uniqueness
constraint on `id` for every known relationship type, which backs
the stale-relationship cleanup `upsert_relation_query` performs on
endpoint changes.

Also creates the range indexes on the pending tag property
(`_pending_job_id`) that commit and rollback use to find a job's
rows: one per label in `PENDING_TAGGED_NODE_LABELS` and one per
known relationship type. The CutoverJob status index and the
candidate schema are created here as well.

## `setup_indexes` \{#agrag-graphdb-neo4j-Neo4jGraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Set up indexes now provided by the store's uniqueness constraints.

Kept as a no-op for callers that provision constraints and indexes in
separate steps. Neo4j creates backing indexes for the `id` and
`merge_key` uniqueness constraints, so creating range indexes for
the same properties would conflict with those constraints.

## `upsert_candidates` \{#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_candidates}

```python
upsert_candidates(candidates:Sequence[CandidateRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> UpsertResult
```

Write candidates without changing nodes that already exist.

## `upsert_nodes` \{#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None, deferred:DeferredWrites | None = None) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

`label` names the batch for constraint/index bookkeeping, matching
every other tracked label; the labels actually written to a node come
from `NodeRecord.labels`, which may name more than one label (for
example a node that is both `Chunk` and `Entity`). Records with
different label sets are grouped and written with separate `MERGE`
queries, since Cypher requires labels to be literal in the query text
rather than a runtime parameter, so `batch_size` chunks apply within
each group rather than across the whole call.

`pending_job_id` tags only the nodes this call creates. A write that
reaches a node the job did not create is not applied and is added to
`deferred`, so a job's rollback cannot change data committed earlier.

**Returns:**

- <code>[UpsertResult](../../common/data_models/graph_record/UpsertResult.md)</code> – The number written or deferred, and one failure entry for each
- <code>[UpsertResult](../../common/data_models/graph_record/UpsertResult.md)</code> – isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive, or `deferred` is
  missing while `pending_job_id` is set.

## `upsert_relations` \{#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None, deferred:DeferredWrites | None = None) -> UpsertResult
```

Write or merge relationships between existing nodes.

Relationship identity is each record's `id`, not its endpoints: see
`upsert_relation_query` for how endpoint changes and same-id
parallel relationships are handled. `pending_job_id` tags only the
relationships this call creates. A write that reaches a relationship
the job did not create is not applied and is added to `deferred`.

**Returns:**

- <code>[UpsertResult](../../common/data_models/graph_record/UpsertResult.md)</code> – The number written or deferred, and one failure entry for each
- <code>[UpsertResult](../../common/data_models/graph_record/UpsertResult.md)</code> – isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive, or `deferred` is
  missing while `pending_job_id` is set.

## `vector_search` \{#agrag-graphdb-neo4j-Neo4jGraphStore-vector_search}

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector using the native vector index.

A label with no provisioned vector index has nothing to search,
so an absent index returns an empty result list rather than a
driver error.

Neo4j's vector procedure applies pending and caller filters only after
selecting its top `k` candidates, so a plain `k=limit` call can
return fewer matches than actually exist. This escalates `k` and
retries until `limit` visible hits come back or the escalation
reaches `_VECTOR_SEARCH_MAX_K`.

**Raises:**

- <code>ValueError</code> – `limit` is not positive. A non-positive value is
  not a meaningful request and would send that same
  non-positive `k` to Neo4j's native vector procedure, which
  requires a positive top-k.
