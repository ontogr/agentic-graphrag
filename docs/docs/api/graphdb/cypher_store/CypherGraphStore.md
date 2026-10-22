---
title: agrag.graphdb.cypher_store.CypherGraphStore
sidebar_label: CypherGraphStore
---

# `agrag.graphdb.cypher_store.CypherGraphStore` \{#agrag-graphdb-cypher_store-CypherGraphStore}

```python
CypherGraphStore(*, tracer:Tracer | None = None) -> None
```

Bases: <code>[GraphStore](../base/GraphStore.md)</code>

A `GraphStore` for databases that run the shared Cypher builders.

Holds the record grouping, batching, per-record failure isolation and label
bookkeeping that every Cypher backend needs. A backend supplies its
connection, query execution, schema statements and error classification.

**Functions:**

- [**blocked_candidate_keys**](#agrag-graphdb-cypher_store-CypherGraphStore-blocked_candidate_keys) – Return keys with a committed candidate that is not pending.
- [**close**](#agrag-graphdb-cypher_store-CypherGraphStore-close) – Release the backend connection.
- [**connect**](#agrag-graphdb-cypher_store-CypherGraphStore-connect) – Open the backend connection and verify connectivity.
- [**ensure_fulltext_index**](#agrag-graphdb-cypher_store-CypherGraphStore-ensure_fulltext_index) – Create a full-text index over node properties if it does not exist.
- [**ensure_unique_constraint**](#agrag-graphdb-cypher_store-CypherGraphStore-ensure_unique_constraint) – Make a property combination unique across the nodes of a label.
- [**ensure_vector_index**](#agrag-graphdb-cypher_store-CypherGraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-cypher_store-CypherGraphStore-execute_read) – Run a read transaction.
- [**execute_write**](#agrag-graphdb-cypher_store-CypherGraphStore-execute_write) – Run a write transaction.
- [**fulltext_copy_set**](#agrag-graphdb-cypher_store-CypherGraphStore-fulltext_copy_set) – Return `SET` clauses a backend needs to keep text searchable.
- [**fulltext_search_call**](#agrag-graphdb-cypher_store-CypherGraphStore-fulltext_search_call) – Build the Cypher fragment that searches a full-text index.
- [**list_indexes**](#agrag-graphdb-cypher_store-CypherGraphStore-list_indexes) – List every index in the database with its readiness.
- [**node_write_extra_set**](#agrag-graphdb-cypher_store-CypherGraphStore-node_write_extra_set) – Return extra `SET` clauses that every node upsert must carry.
- [**register_labels**](#agrag-graphdb-cypher_store-CypherGraphStore-register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag-graphdb-cypher_store-CypherGraphStore-register_relation_types) – Add types to this instance's known-relation-type set.
- [**run_in_transaction**](#agrag-graphdb-cypher_store-CypherGraphStore-run_in_transaction) – Run work with a transaction handle and return its result.
- [**session**](#agrag-graphdb-cypher_store-CypherGraphStore-session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag-graphdb-cypher_store-CypherGraphStore-setup_constraints) – Create per-label and per-relation-type uniqueness constraints.
- [**setup_indexes**](#agrag-graphdb-cypher_store-CypherGraphStore-setup_indexes) – Create per-label property indexes.
- [**shortest_path_distance_query**](#agrag-graphdb-cypher_store-CypherGraphStore-shortest_path_distance_query) – Build the Cypher that measures the shortest committed path.
- [**upsert_candidates**](#agrag-graphdb-cypher_store-CypherGraphStore-upsert_candidates) – Write candidates without changing nodes that already exist.
- [**upsert_nodes**](#agrag-graphdb-cypher_store-CypherGraphStore-upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag-graphdb-cypher_store-CypherGraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-cypher_store-CypherGraphStore-vector_search) – Search nodes by dense vector using the native vector index.
- [**vector_search_call**](#agrag-graphdb-cypher_store-CypherGraphStore-vector_search_call) – Build the Cypher fragment that searches a vector index.
- [**vector_value**](#agrag-graphdb-cypher_store-CypherGraphStore-vector_value) – Wrap a Cypher expression that holds an embedding for a property write.

**Parameters:**

- **tracer** (<code>Tracer | None</code>) – Opens every span this store's methods produce.

## `blocked_candidate_keys` \{#agrag-graphdb-cypher_store-CypherGraphStore-blocked_candidate_keys}

```python
blocked_candidate_keys(keys:Sequence[str]) -> set[str]
```

Return keys with a committed candidate that is not pending.

## `close` \{#agrag-graphdb-cypher_store-CypherGraphStore-close}

```python
close() -> None
```

Release the backend connection.

## `connect` \{#agrag-graphdb-cypher_store-CypherGraphStore-connect}

```python
connect() -> None
```

Open the backend connection and verify connectivity.

## `ensure_fulltext_index` \{#agrag-graphdb-cypher_store-CypherGraphStore-ensure_fulltext_index}

```python
ensure_fulltext_index(*, label:str, properties:Sequence[str]) -> None
```

Create a full-text index over node properties if it does not exist.

The index is built from the node text of the given properties. Its
name is derived from the label and the properties, so a repeated call
with the same arguments does nothing.

**Parameters:**

- **label** (<code>str</code>) – The node label to index.
- **properties** (<code>Sequence\[str\]</code>) – The property names to index. Each must be a safe
  identifier.

**Raises:**

- <code>ValueError</code> – `properties` is empty, or a name is not a safe
  identifier.

## `ensure_unique_constraint` \{#agrag-graphdb-cypher_store-CypherGraphStore-ensure_unique_constraint}

```python
ensure_unique_constraint(*, label:str, properties:Sequence[str]) -> None
```

Make a property combination unique across the nodes of a label.

Does nothing when the constraint already exists. A backend that builds
constraints in the background returns once this one is usable.

**Parameters:**

- **label** (<code>str</code>) – The node label.
- **properties** (<code>Sequence\[str\]</code>) – The property names whose combination must be unique.

**Raises:**

- <code>ValueError</code> – `properties` is empty, or a name is not a safe
  identifier.

## `ensure_vector_index` \{#agrag-graphdb-cypher_store-CypherGraphStore-ensure_vector_index}

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

## `execute_read` \{#agrag-graphdb-cypher_store-CypherGraphStore-execute_read}

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

## `execute_write` \{#agrag-graphdb-cypher_store-CypherGraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

## `fulltext_copy_set` \{#agrag-graphdb-cypher_store-CypherGraphStore-fulltext_copy_set}

```python
fulltext_copy_set(alias:str, source:str, properties:Iterable[str]) -> str
```

Return `SET` clauses a backend needs to keep text searchable.

**Parameters:**

- **alias** (<code>str</code>) – The Cypher variable of the node being written.
- **source** (<code>str</code>) – A Cypher map expression that holds the written properties.
- **properties** (<code>Iterable\[str\]</code>) – The text properties that have a full-text index.

**Returns:**

- <code>str</code> – Clauses to add to the write, or an empty string when the backend
- <code>str</code> – searches the stored text directly.

## `fulltext_search_call` \{#agrag-graphdb-cypher_store-CypherGraphStore-fulltext_search_call}

```python
fulltext_search_call(*, label:str, properties:Sequence[str]) -> SearchCall
```

Build the Cypher fragment that searches a full-text index.

**Parameters:**

- **label** (<code>str</code>) – The node label the index covers.
- **properties** (<code>Sequence\[str\]</code>) – The indexed property names, as passed to
  `ensure_fulltext_index`.

**Returns:**

- <code>[SearchCall](../../common/data_models/index_record/SearchCall.md)</code> – A fragment that yields `node` and `score` and expects
- <code>[SearchCall](../../common/data_models/index_record/SearchCall.md)</code> – `$fulltext_terms` and `$k`.

**Raises:**

- <code>ValueError</code> – `label` or a property is not a safe identifier.

## `list_indexes` \{#agrag-graphdb-cypher_store-CypherGraphStore-list_indexes}

```python
list_indexes(*, timeout:float | None = None) -> list[IndexInfo]
```

List every index in the database with its readiness.

**Parameters:**

- **timeout** (<code>float | None</code>) – Server-side timeout in seconds. None uses the server's
  default.

**Returns:**

- <code>list\[[IndexInfo](../../common/data_models/index_record/IndexInfo.md)\]</code> – One entry per index, including indexes that are still building.

## `node_write_extra_set` \{#agrag-graphdb-cypher_store-CypherGraphStore-node_write_extra_set}

```python
node_write_extra_set() -> str
```

Return extra `SET` clauses that every node upsert must carry.

**Returns:**

- <code>str</code> – Clauses for a node upsert query, which can read `record.properties`,
- <code>str</code> – or an empty string when the backend stores the properties as given.

## `register_labels` \{#agrag-graphdb-cypher_store-CypherGraphStore-register_labels}

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>ValueError</code> – Any label is not a safe identifier.

## `register_relation_types` \{#agrag-graphdb-cypher_store-CypherGraphStore-register_relation_types}

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>Sequence\[str\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>ValueError</code> – Any type is not a safe identifier.

## `run_in_transaction` \{#agrag-graphdb-cypher_store-CypherGraphStore-run_in_transaction}

```python
run_in_transaction(work:Callable[[GraphStoreTransaction], Awaitable[_T]]) -> _T
```

Run work with a transaction handle and return its result.

The default implementation passes this store to `work` and provides
no atomicity across calls. Backends may provide a real transaction.
A transactional backend commits when `work` returns and rolls back
when it raises. A backend may retry transient failures, so `work`
must return results rather than change state outside the callback.

**Parameters:**

- **work** (<code>Callable\[\[[GraphStoreTransaction](../base/GraphStoreTransaction.md)\], Awaitable\[\_T\]\]</code>) – The reads and writes to run together. Must be safe to retry.

**Returns:**

- <code>\_T</code> – Whatever `work` returns.

## `session` \{#agrag-graphdb-cypher_store-CypherGraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>AbstractAsyncContextManager\[Any\]</code> – A context manager yielding a backend session.

## `setup_constraints` \{#agrag-graphdb-cypher_store-CypherGraphStore-setup_constraints}

```python
setup_constraints() -> None
```

Create per-label and per-relation-type uniqueness constraints.

Constraints cover every node label and relationship type written
through this instance or already present in the database, so a fresh
instance can set up an existing database without first rewriting
every record.

## `setup_indexes` \{#agrag-graphdb-cypher_store-CypherGraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Create per-label property indexes.

Covers every node label written through this instance or already
present in the database, so a fresh instance can set up an existing
database without first rewriting every record.

## `shortest_path_distance_query` \{#agrag-graphdb-cypher_store-CypherGraphStore-shortest_path_distance_query}

```python
shortest_path_distance_query() -> str
```

Build the Cypher that measures the shortest committed path.

**Returns:**

- <code>str</code> – A parameterized query expecting `$seed_ids` and `$target_ids`
- <code>str</code> – that returns a `dist` for each pair joined by a path.

## `upsert_candidates` \{#agrag-graphdb-cypher_store-CypherGraphStore-upsert_candidates}

```python
upsert_candidates(candidates:Sequence[CandidateRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> UpsertResult
```

Write candidates without changing nodes that already exist.

## `upsert_nodes` \{#agrag-graphdb-cypher_store-CypherGraphStore-upsert_nodes}

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

## `upsert_relations` \{#agrag-graphdb-cypher_store-CypherGraphStore-upsert_relations}

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

## `vector_search` \{#agrag-graphdb-cypher_store-CypherGraphStore-vector_search}

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

## `vector_search_call` \{#agrag-graphdb-cypher_store-CypherGraphStore-vector_search_call}

```python
vector_search_call(*, label:str, vector_property:str) -> SearchCall
```

Build the Cypher fragment that searches a vector index.

**Parameters:**

- **label** (<code>str</code>) – The node label the index covers.
- **vector_property** (<code>str</code>) – The embedding property name.

**Returns:**

- <code>[SearchCall](../../common/data_models/index_record/SearchCall.md)</code> – A fragment that yields `node` and `score` and expects
- <code>[SearchCall](../../common/data_models/index_record/SearchCall.md)</code> – `$vector` and `$k`. `score` uses the same scale on every
- **backend** (<code>[SearchCall](../../common/data_models/index_record/SearchCall.md)</code>) – higher is closer.

**Raises:**

- <code>ValueError</code> – `label` or `vector_property` is not a safe
  identifier.

## `vector_value` \{#agrag-graphdb-cypher_store-CypherGraphStore-vector_value}

```python
vector_value(expression:str) -> str
```

Wrap a Cypher expression that holds an embedding for a property write.

**Parameters:**

- **expression** (<code>str</code>) – A Cypher expression that evaluates to a list of floats.

**Returns:**

- <code>str</code> – The expression to assign to a vector property. Backends that store
- <code>str</code> – a plain float list return `expression` unchanged.
