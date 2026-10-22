---
title: agrag.graphdb.falkordb.FalkorDBGraphStore
sidebar_label: FalkorDBGraphStore
---

# `agrag.graphdb.falkordb.FalkorDBGraphStore` \{#agrag-graphdb-falkordb-FalkorDBGraphStore}

```python
FalkorDBGraphStore(*, settings:FalkorDBSettings | None = None, client:FalkorDB | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[CypherGraphStore](../cypher_store/CypherGraphStore.md)</code>

A `GraphStore` backed by FalkorDB, using native vector indexes.

The client connects lazily on first use, so constructing the store does not
open a network connection. Each query is atomic on its own. A callback
passed to `run_in_transaction` runs its statements in order with no
rollback, so callers keep every statement of such a group safe to repeat.

**Functions:**

- [**blocked_candidate_keys**](#agrag-graphdb-falkordb-FalkorDBGraphStore-blocked_candidate_keys) – Return keys with a committed candidate that is not pending.
- [**close**](#agrag-graphdb-falkordb-FalkorDBGraphStore-close) – Close the client, releasing its connection pool.
- [**connect**](#agrag-graphdb-falkordb-FalkorDBGraphStore-connect) – Open the client and verify connectivity and server settings.
- [**ensure_fulltext_index**](#agrag-graphdb-falkordb-FalkorDBGraphStore-ensure_fulltext_index) – Create a full-text index over node properties if it does not exist.
- [**ensure_unique_constraint**](#agrag-graphdb-falkordb-FalkorDBGraphStore-ensure_unique_constraint) – Make a property combination unique across the nodes of a label.
- [**ensure_vector_index**](#agrag-graphdb-falkordb-FalkorDBGraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-falkordb-FalkorDBGraphStore-execute_read) – Run a read query and return its rows.
- [**execute_write**](#agrag-graphdb-falkordb-FalkorDBGraphStore-execute_write) – Run a write query and return its rows.
- [**fulltext_copy_set**](#agrag-graphdb-falkordb-FalkorDBGraphStore-fulltext_copy_set) – Return `SET` clauses that keep the search copies of text properties.
- [**fulltext_search_call**](#agrag-graphdb-falkordb-FalkorDBGraphStore-fulltext_search_call) – Build the Cypher fragment that searches a full-text index.
- [**list_indexes**](#agrag-graphdb-falkordb-FalkorDBGraphStore-list_indexes) – List every index in the database with its readiness.
- [**node_write_extra_set**](#agrag-graphdb-falkordb-FalkorDBGraphStore-node_write_extra_set) – Return the clauses that store vectors and search copies on upsert.
- [**register_labels**](#agrag-graphdb-falkordb-FalkorDBGraphStore-register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag-graphdb-falkordb-FalkorDBGraphStore-register_relation_types) – Add types to this instance's known-relation-type set.
- [**run_in_transaction**](#agrag-graphdb-falkordb-FalkorDBGraphStore-run_in_transaction) – Run work with a transaction handle and return its result.
- [**session**](#agrag-graphdb-falkordb-FalkorDBGraphStore-session) – Open a session. FalkorDB has none, so the session is the store.
- [**setup_constraints**](#agrag-graphdb-falkordb-FalkorDBGraphStore-setup_constraints) – Create `id` and `merge_key` uniqueness constraints per label.
- [**setup_indexes**](#agrag-graphdb-falkordb-FalkorDBGraphStore-setup_indexes) – Set up indexes now provided by the store's uniqueness constraints.
- [**shortest_path_distance_query**](#agrag-graphdb-falkordb-FalkorDBGraphStore-shortest_path_distance_query) – Build the path-distance query within a bounded number of hops.
- [**upsert_candidates**](#agrag-graphdb-falkordb-FalkorDBGraphStore-upsert_candidates) – Write candidates without changing nodes that already exist.
- [**upsert_nodes**](#agrag-graphdb-falkordb-FalkorDBGraphStore-upsert_nodes) – Write or merge nodes, refusing an embedding of the wrong length.
- [**upsert_relations**](#agrag-graphdb-falkordb-FalkorDBGraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-falkordb-FalkorDBGraphStore-vector_search) – Search nodes by dense vector using the native vector index.
- [**vector_search_call**](#agrag-graphdb-falkordb-FalkorDBGraphStore-vector_search_call) – Build the Cypher fragment that searches a vector index.
- [**vector_value**](#agrag-graphdb-falkordb-FalkorDBGraphStore-vector_value) – Wrap a float-list expression so FalkorDB stores it as a vector.

**Parameters:**

- **settings** (<code>[FalkorDBSettings](../settings/FalkorDBSettings.md) | None</code>) – Connection settings. Defaults to `FalkorDBSettings()`.
- **client** (<code>FalkorDB | None</code>) – A pre-built `falkordb.asyncio.FalkorDB` client, for tests.
- **tracer** (<code>Tracer | None</code>) – Opens every span this store's methods produce.

## `blocked_candidate_keys` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-blocked_candidate_keys}

```python
blocked_candidate_keys(keys:Sequence[str]) -> set[str]
```

Return keys with a committed candidate that is not pending.

## `close` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-close}

```python
close() -> None
```

Close the client, releasing its connection pool.

## `connect` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-connect}

```python
connect() -> None
```

Open the client and verify connectivity and server settings.

**Raises:**

- <code>[GraphStoreError](../errors/GraphStoreError.md)</code> – The server module is older than the tested minimum,
  or a server limit would silently cut results.

## `ensure_fulltext_index` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-ensure_fulltext_index}

```python
ensure_fulltext_index(*, label:str, properties:Sequence[str]) -> None
```

Create a full-text index over node properties if it does not exist.

Nodes that already hold text for a newly indexed property get their
search copy written here, since the write path only copies text it sees.

## `ensure_unique_constraint` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-ensure_unique_constraint}

```python
ensure_unique_constraint(*, label:str, properties:Sequence[str]) -> None
```

Make a property combination unique across the nodes of a label.

## `ensure_vector_index` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

An index that already exists keeps its own dimension and similarity
function, and the store uses those for later writes and searches.

**Raises:**

- <code>[EmbeddingDimensionMismatchError](../../embedding/errors/EmbeddingDimensionMismatchError.md)</code> – The index exists with a different
  dimension.
- <code>ValueError</code> – `distance` is not supported, a name is unsafe, or the
  index exists with a different similarity function.

## `execute_read` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-execute_read}

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read query and return its rows.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.
- **timeout** (<code>float | None</code>) – Server-side timeout in seconds. The database stops the query
  when it runs longer. None uses the server's default.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

## `execute_write` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write query and return its rows.

**Raises:**

- <code>[GraphStoreConstraintViolationError](../errors/GraphStoreConstraintViolationError.md)</code> – The write violated a uniqueness
  constraint.

## `fulltext_copy_set` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-fulltext_copy_set}

```python
fulltext_copy_set(alias:str, source:str, properties:Iterable[str]) -> str
```

Return `SET` clauses that keep the search copies of text properties.

**Parameters:**

- **alias** (<code>str</code>) – The Cypher variable of the node being written.
- **source** (<code>str</code>) – A Cypher map expression that holds the written properties.
- **properties** (<code>Iterable\[str\]</code>) – The text properties that have a full-text index.

**Returns:**

- <code>str</code> – The clauses, or an empty string when there is nothing to copy.

## `fulltext_search_call` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-fulltext_search_call}

```python
fulltext_search_call(*, label:str, properties:Sequence[str]) -> SearchCall
```

Build the Cypher fragment that searches a full-text index.

The match is restricted to the search copies of `properties`, so a
term that appears only in another indexed property of `label` does
not match. FalkorDB scores a match with TF-IDF, which is 0 for a word
every document holds. One is added so that a match always scores above
0\.

The fragment ends with `LIMIT $k`. On FalkorDB 4.22.2 a `WHERE` that
a caller appends after it is applied before the limit, so the call still
returns up to `k` matching rows.

**Raises:**

- <code>ValueError</code> – `properties` is empty, or a name is not a safe
  identifier.

## `list_indexes` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-list_indexes}

```python
list_indexes(*, timeout:float | None = None) -> list[IndexInfo]
```

List every index in the database with its readiness.

## `node_write_extra_set` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-node_write_extra_set}

```python
node_write_extra_set() -> str
```

Return the clauses that store vectors and search copies on upsert.

## `register_labels` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-register_labels}

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>ValueError</code> – Any label is not a safe identifier.

## `register_relation_types` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-register_relation_types}

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>Sequence\[str\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>ValueError</code> – Any type is not a safe identifier.

## `run_in_transaction` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-run_in_transaction}

```python
run_in_transaction(work:Callable[[GraphStoreTransaction], Awaitable[_T]]) -> _T
```

Run work with a transaction handle and return its result.

The statements run in order, one after the other from this process,
and are not rolled back if a later one fails. Keep every statement of
`work` safe to repeat.

**Parameters:**

- **work** (<code>Callable\[\[[GraphStoreTransaction](../base/GraphStoreTransaction.md)\], Awaitable\[\_T\]\]</code>) – The reads and writes to run together.

**Returns:**

- <code>\_T</code> – Whatever `work` returns.

**Raises:**

- <code>[GraphStoreConstraintViolationError](../errors/GraphStoreConstraintViolationError.md)</code> – A statement violated a
  uniqueness constraint.

## `session` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session. FalkorDB has none, so the session is the store.

## `setup_constraints` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-setup_constraints}

```python
setup_constraints() -> None
```

Create `id` and `merge_key` uniqueness constraints per label.

Covers every label and relationship type written through this
instance or already in the database, plus the fixed constraints and
indexes the write paths rely on. Constraints are built in the
background, so this returns once each one is operational.

## `setup_indexes` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Set up indexes now provided by the store's uniqueness constraints.

Kept as a no-op for callers that provision constraints and indexes in
separate steps: `setup_constraints` creates the exact-match indexes
its constraints need.

## `shortest_path_distance_query` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-shortest_path_distance_query}

```python
shortest_path_distance_query() -> str
```

Build the path-distance query within a bounded number of hops.

FalkorDB's `shortestPath` cannot skip rows that belong to an
in-flight job, so the query takes the shortest committed path among the
paths of up to `MAX_PATH_HOPS` relationships.

## `upsert_candidates` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-upsert_candidates}

```python
upsert_candidates(candidates:Sequence[CandidateRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> UpsertResult
```

Write candidates without changing nodes that already exist.

## `upsert_nodes` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None, deferred:DeferredWrites | None = None) -> UpsertResult
```

Write or merge nodes, refusing an embedding of the wrong length.

FalkorDB accepts a vector of any length into a vector index without an
error and then never returns it, so a record whose embedding does not
match the index dimension is reported as a failure instead.

## `upsert_relations` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-upsert_relations}

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

## `vector_search` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-vector_search}

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector using the native vector index.

A label with no provisioned vector index has nothing to search,
so an absent index returns an empty result list rather than a
driver error.

The native index selects candidates before pending and caller filters
apply, so a plain `k=limit` call can
return fewer matches than actually exist. This escalates `k` and
retries until `limit` visible hits come back or the escalation
reaches `_VECTOR_SEARCH_MAX_K`.

**Raises:**

- <code>ValueError</code> – `limit` is not positive. Validation runs before
  the backend query.

## `vector_search_call` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-vector_search_call}

```python
vector_search_call(*, label:str, vector_property:str) -> SearchCall
```

Build the Cypher fragment that searches a vector index.

FalkorDB scores a match by distance, lowest first. The fragment turns
that into the score Neo4j reports: cosine `1 - distance / 2`,
euclidean `1 / (1 + distance ^ 2)`.

## `vector_value` \{#agrag-graphdb-falkordb-FalkorDBGraphStore-vector_value}

```python
vector_value(expression:str) -> str
```

Wrap a float-list expression so FalkorDB stores it as a vector.

A null expression stays null, so a missing embedding is not an error.
