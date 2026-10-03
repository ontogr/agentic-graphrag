---
title: agrag.graphdb
sidebar_position: 7
---

## `agrag.graphdb` \{#agrag-graphdb}

Graph storage backends and the build shortcut.

**Modules:**

- [**base**](#agrag-graphdb-base) – The GraphStore abstraction and its build shortcut helpers.
- [**entities**](#agrag-graphdb-entities) – Load persisted entities by id.
- [**errors**](#agrag-graphdb-errors) – Errors that the graph-store layer raises.
- [**neo4j**](#agrag-graphdb-neo4j) – Neo4j graph-store backend.
- [**serialize**](#agrag-graphdb-serialize) – Convert graph records to driver parameters and graph node rows to models.
- [**settings**](#agrag-graphdb-settings) – Settings for the Neo4j graph-store backend.

**Classes:**

- [**GraphStore**](#agrag-graphdb-GraphStore) – A graph database backend: schema, writes, and native vector search.
- [**GraphStoreError**](#agrag-graphdb-GraphStoreError) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](#agrag-graphdb-GraphStoreMissingExtraError) – A graph store exists, but its package extra is not installed.
- [**Neo4jGraphStore**](#agrag-graphdb-Neo4jGraphStore) – A `GraphStore` backed by Neo4j, using native vector indexes.
- [**Neo4jSettings**](#agrag-graphdb-Neo4jSettings) – Neo4j connection configuration.

**Functions:**

- [**build_graph_store**](#agrag-graphdb-build_graph_store) – Build a graph store from a backend name, or return one unchanged.

**Attributes:**

- [**GraphStoreName**](#agrag-graphdb-GraphStoreName) –

### `agrag.graphdb.GraphStore` \{#agrag-graphdb-GraphStore}

Bases: <code>ABC</code>

A graph database backend: schema, writes, and native vector search.

**Functions:**

- [**close**](#agrag-graphdb-GraphStore-close) – Release the backend connection.
- [**connect**](#agrag-graphdb-GraphStore-connect) – Open the backend connection and verify connectivity.
- [**ensure_vector_index**](#agrag-graphdb-GraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-GraphStore-execute_read) – Run a read transaction.
- [**execute_write**](#agrag-graphdb-GraphStore-execute_write) – Run a write transaction.
- [**register_labels**](#agrag-graphdb-GraphStore-register_labels) – Mark labels as known, without writing anything.
- [**register_relation_types**](#agrag-graphdb-GraphStore-register_relation_types) – Mark relationship types as known, without writing anything.
- [**session**](#agrag-graphdb-GraphStore-session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag-graphdb-GraphStore-setup_constraints) – Create per-label and per-relation-type uniqueness constraints.
- [**setup_indexes**](#agrag-graphdb-GraphStore-setup_indexes) – Create per-label property indexes.
- [**transaction**](#agrag-graphdb-GraphStore-transaction) – Start an explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag-graphdb-GraphStore-upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag-graphdb-GraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-GraphStore-vector_search) – Search nodes by dense vector.

#### `agrag.graphdb.GraphStore.close` \{#agrag-graphdb-GraphStore-close}

```python
close() -> None
```

Release the backend connection.

#### `agrag.graphdb.GraphStore.connect` \{#agrag-graphdb-GraphStore-connect}

```python
connect() -> None
```

Open the backend connection and verify connectivity.

#### `agrag.graphdb.GraphStore.ensure_vector_index` \{#agrag-graphdb-GraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>str</code>) – The node label to index.
- **vector_property** (<code>str</code>) – The embedding property name.
- **dimensions** (<code>int</code>) – The embedding dimension. If the index already exists
  with a different dimension, this raises.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric.

**Raises:**

- <code>EmbeddingDimensionMismatchError</code> – The index already exists with a
  different dimension than `dimensions`.

#### `agrag.graphdb.GraphStore.execute_read` \{#agrag-graphdb-GraphStore-execute_read}

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

#### `agrag.graphdb.GraphStore.execute_write` \{#agrag-graphdb-GraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

#### `agrag.graphdb.GraphStore.register_labels` \{#agrag-graphdb-GraphStore-register_labels}

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

#### `agrag.graphdb.GraphStore.register_relation_types` \{#agrag-graphdb-GraphStore-register_relation_types}

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

#### `agrag.graphdb.GraphStore.session` \{#agrag-graphdb-GraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>AbstractAsyncContextManager\[Any\]</code> – A context manager yielding a backend session.

#### `agrag.graphdb.GraphStore.setup_constraints` \{#agrag-graphdb-GraphStore-setup_constraints}

```python
setup_constraints() -> None
```

Create per-label and per-relation-type uniqueness constraints.

Constraints cover every node label and relationship type written
through this instance or already present in the database, so a fresh
instance can set up an existing database without first rewriting
every record.

#### `agrag.graphdb.GraphStore.setup_indexes` \{#agrag-graphdb-GraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Create per-label property indexes.

Covers every node label written through this instance or already
present in the database, so a fresh instance can set up an existing
database without first rewriting every record.

#### `agrag.graphdb.GraphStore.transaction` \{#agrag-graphdb-GraphStore-transaction}

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

- <code>AsyncIterator\[[GraphStoreTransaction](#agrag-graphdb-base-GraphStoreTransaction)\]</code> – An async context manager yielding the transactional handle.

#### `agrag.graphdb.GraphStore.upsert_nodes` \{#agrag-graphdb-GraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

**Parameters:**

- **label** (<code>str</code>) – The label this batch is tracked under for constraint and
  index bookkeeping.
- **nodes** (<code>Sequence\[[NodeRecord](common.md#agrag-common-data_models-graph_record-NodeRecord)\]</code>) – The node records to upsert. Each node's `NodeRecord.labels`
  names the full label set actually written to it, which may
  include labels beyond `label`.
- **batch_size** (<code>int</code>) – Records per backend write call, applied within each
  distinct label set when `nodes` mixes more than one. Must
  be positive.

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

#### `agrag.graphdb.GraphStore.upsert_relations` \{#agrag-graphdb-GraphStore-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>Sequence\[[RelationRecord](common.md#agrag-common-data_models-graph_record-RelationRecord)\]</code>) – The relation records to upsert.
- **batch_size** (<code>int</code>) – Records per backend write call. Must be positive.

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

#### `agrag.graphdb.GraphStore.vector_search` \{#agrag-graphdb-GraphStore-vector_search}

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

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

### `agrag.graphdb.GraphStoreError` \{#agrag-graphdb-GraphStoreError}

Bases: <code>Exception</code>

The base class for every graph-store error.

### `agrag.graphdb.GraphStoreMissingExtraError` \{#agrag-graphdb-GraphStoreMissingExtraError}

```python
GraphStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[GraphStoreError](#agrag-graphdb-errors-GraphStoreError)</code>

A graph store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-graphdb-GraphStoreMissingExtraError-extra) – The name of the package extra to install.

#### `agrag.graphdb.GraphStoreMissingExtraError.extra` \{#agrag-graphdb-GraphStoreMissingExtraError-extra}

```python
extra = extra
```

### `agrag.graphdb.GraphStoreName` \{#agrag-graphdb-GraphStoreName}

```python
GraphStoreName = Literal['neo4j']
```

### `agrag.graphdb.Neo4jGraphStore` \{#agrag-graphdb-Neo4jGraphStore}

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[GraphStore](#agrag-graphdb-base-GraphStore)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop.

**Functions:**

- [**close**](#agrag-graphdb-Neo4jGraphStore-close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag-graphdb-Neo4jGraphStore-connect) – Open the driver and verify connectivity.
- [**ensure_relation_constraint**](#agrag-graphdb-Neo4jGraphStore-ensure_relation_constraint) – Create a relationship type's `id` uniqueness constraint once.
- [**ensure_vector_index**](#agrag-graphdb-Neo4jGraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-Neo4jGraphStore-execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag-graphdb-Neo4jGraphStore-execute_write) – Run a write transaction and return its rows.
- [**register_labels**](#agrag-graphdb-Neo4jGraphStore-register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag-graphdb-Neo4jGraphStore-register_relation_types) – Add types to this instance's known-relation-type set.
- [**session**](#agrag-graphdb-Neo4jGraphStore-session) – Open a session to the configured database.
- [**setup_constraints**](#agrag-graphdb-Neo4jGraphStore-setup_constraints) – Create `id` and `merge_key` uniqueness constraints per label.
- [**setup_indexes**](#agrag-graphdb-Neo4jGraphStore-setup_indexes) – Set up indexes now provided by the store's uniqueness constraints.
- [**transaction**](#agrag-graphdb-Neo4jGraphStore-transaction) – Open one Neo4j explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag-graphdb-Neo4jGraphStore-upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag-graphdb-Neo4jGraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-Neo4jGraphStore-vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](#agrag-graphdb-settings-Neo4jSettings) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>AsyncDriver | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this store's methods produce.

#### `agrag.graphdb.Neo4jGraphStore.close` \{#agrag-graphdb-Neo4jGraphStore-close}

```python
close() -> None
```

Close the driver, releasing its connection pool.

#### `agrag.graphdb.Neo4jGraphStore.connect` \{#agrag-graphdb-Neo4jGraphStore-connect}

```python
connect() -> None
```

Open the driver and verify connectivity.

#### `agrag.graphdb.Neo4jGraphStore.ensure_relation_constraint` \{#agrag-graphdb-Neo4jGraphStore-ensure_relation_constraint}

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

#### `agrag.graphdb.Neo4jGraphStore.ensure_vector_index` \{#agrag-graphdb-Neo4jGraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

A concurrent creator can commit the same index after this operation
starts. Neo4j reports that race as an equivalent-schema error, which
means the requested index already exists.

**Raises:**

- <code>[EmbeddingDimensionMismatchError](embedding.md#agrag-embedding-errors-EmbeddingDimensionMismatchError)</code> – The index already exists with a
  different dimension than `dimensions`.

#### `agrag.graphdb.Neo4jGraphStore.execute_read` \{#agrag-graphdb-Neo4jGraphStore-execute_read}

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

#### `agrag.graphdb.Neo4jGraphStore.execute_write` \{#agrag-graphdb-Neo4jGraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag-graphdb-errors-GraphStoreConstraintViolationError)</code> – The write violated a uniqueness
  constraint, translated from the driver's own exception so
  callers do not need a hard dependency on it.

#### `agrag.graphdb.Neo4jGraphStore.register_labels` \{#agrag-graphdb-Neo4jGraphStore-register_labels}

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>ValueError</code> – Any label is not a safe identifier.

#### `agrag.graphdb.Neo4jGraphStore.register_relation_types` \{#agrag-graphdb-Neo4jGraphStore-register_relation_types}

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>Sequence\[str\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>ValueError</code> – Any type is not a safe identifier.

#### `agrag.graphdb.Neo4jGraphStore.session` \{#agrag-graphdb-Neo4jGraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

#### `agrag.graphdb.Neo4jGraphStore.setup_constraints` \{#agrag-graphdb-Neo4jGraphStore-setup_constraints}

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

#### `agrag.graphdb.Neo4jGraphStore.setup_indexes` \{#agrag-graphdb-Neo4jGraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Set up indexes now provided by the store's uniqueness constraints.

Kept as a no-op for callers that provision constraints and indexes in
separate steps. Neo4j creates backing indexes for the `id` and
`merge_key` uniqueness constraints, so creating range indexes for
the same properties would conflict with those constraints.

#### `agrag.graphdb.Neo4jGraphStore.transaction` \{#agrag-graphdb-Neo4jGraphStore-transaction}

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Open one Neo4j explicit transaction spanning multiple writes.

Commits when the `async with` block exits cleanly; rolls back and
re-raises when it raises. The identity constraint is ensured before
opening the transaction, the same way `upsert_nodes` ensures it
before writing, since `_Neo4jTransaction.upsert_nodes` skips that
check to avoid a nested write racing the transaction it belongs to.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag-graphdb-errors-GraphStoreConstraintViolationError)</code> – A write inside the block, or the
  commit itself, violated a uniqueness constraint -- Neo4j
  validates some constraints only at commit time for an
  explicit transaction, so this can surface here even when
  every individual write appeared to succeed.

#### `agrag.graphdb.Neo4jGraphStore.upsert_nodes` \{#agrag-graphdb-Neo4jGraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
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

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

#### `agrag.graphdb.Neo4jGraphStore.upsert_relations` \{#agrag-graphdb-Neo4jGraphStore-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

Relationship identity is each record's `id`, not its endpoints: see
`upsert_relation_query` for how endpoint changes and same-id
parallel relationships are handled.

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

#### `agrag.graphdb.Neo4jGraphStore.vector_search` \{#agrag-graphdb-Neo4jGraphStore-vector_search}

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

### `agrag.graphdb.Neo4jSettings` \{#agrag-graphdb-Neo4jSettings}

Bases: <code>BaseSettings</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag-graphdb-Neo4jSettings-uri) (<code>str</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag-graphdb-Neo4jSettings-username) (<code>str</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag-graphdb-Neo4jSettings-password) (<code>SecretStr</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag-graphdb-Neo4jSettings-database) (<code>str</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag-graphdb-Neo4jSettings-max_connection_lifetime) (<code>int</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

**Raises:**

- <code>ValueError</code> – `uri` is plaintext (`bolt://` or `neo4j://`) and
  points at a non-local host. Neo4j always authenticates with a
  password, so a plaintext scheme always sends it in the clear; use
  `neo4j+s://` (or `bolt+s://`) for a remote instance.

#### `agrag.graphdb.Neo4jSettings.database` \{#agrag-graphdb-Neo4jSettings-database}

```python
database: str = 'neo4j'
```

#### `agrag.graphdb.Neo4jSettings.max_connection_lifetime` \{#agrag-graphdb-Neo4jSettings-max_connection_lifetime}

```python
max_connection_lifetime: int = 240
```

#### `agrag.graphdb.Neo4jSettings.model_config` \{#agrag-graphdb-Neo4jSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.graphdb.Neo4jSettings.password` \{#agrag-graphdb-Neo4jSettings-password}

```python
password: SecretStr = SecretStr('neo4j')
```

#### `agrag.graphdb.Neo4jSettings.uri` \{#agrag-graphdb-Neo4jSettings-uri}

```python
uri: str = 'bolt://localhost:7687'
```

#### `agrag.graphdb.Neo4jSettings.username` \{#agrag-graphdb-Neo4jSettings-username}

```python
username: str = 'neo4j'
```

### `agrag.graphdb.base` \{#agrag-graphdb-base}

The GraphStore abstraction and its build shortcut helpers.

**Classes:**

- [**GraphStore**](#agrag-graphdb-base-GraphStore) – A graph database backend: schema, writes, and native vector search.
- [**GraphStoreTransaction**](#agrag-graphdb-base-GraphStoreTransaction) – The read/write/upsert surface available inside a `transaction()` block.

#### `agrag.graphdb.base.GraphStore` \{#agrag-graphdb-base-GraphStore}

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

##### `agrag.graphdb.base.GraphStore.close` \{#agrag-graphdb-base-GraphStore-close}

```python
close() -> None
```

Release the backend connection.

##### `agrag.graphdb.base.GraphStore.connect` \{#agrag-graphdb-base-GraphStore-connect}

```python
connect() -> None
```

Open the backend connection and verify connectivity.

##### `agrag.graphdb.base.GraphStore.ensure_vector_index` \{#agrag-graphdb-base-GraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>str</code>) – The node label to index.
- **vector_property** (<code>str</code>) – The embedding property name.
- **dimensions** (<code>int</code>) – The embedding dimension. If the index already exists
  with a different dimension, this raises.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric.

**Raises:**

- <code>EmbeddingDimensionMismatchError</code> – The index already exists with a
  different dimension than `dimensions`.

##### `agrag.graphdb.base.GraphStore.execute_read` \{#agrag-graphdb-base-GraphStore-execute_read}

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

##### `agrag.graphdb.base.GraphStore.execute_write` \{#agrag-graphdb-base-GraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>str</code>) – The Cypher query to run.
- **parameters** (<code>Mapping\[str, Any\] | None</code>) – The query parameters.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The result rows as dicts.

##### `agrag.graphdb.base.GraphStore.register_labels` \{#agrag-graphdb-base-GraphStore-register_labels}

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

##### `agrag.graphdb.base.GraphStore.register_relation_types` \{#agrag-graphdb-base-GraphStore-register_relation_types}

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

##### `agrag.graphdb.base.GraphStore.session` \{#agrag-graphdb-base-GraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>AbstractAsyncContextManager\[Any\]</code> – A context manager yielding a backend session.

##### `agrag.graphdb.base.GraphStore.setup_constraints` \{#agrag-graphdb-base-GraphStore-setup_constraints}

```python
setup_constraints() -> None
```

Create per-label and per-relation-type uniqueness constraints.

Constraints cover every node label and relationship type written
through this instance or already present in the database, so a fresh
instance can set up an existing database without first rewriting
every record.

##### `agrag.graphdb.base.GraphStore.setup_indexes` \{#agrag-graphdb-base-GraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Create per-label property indexes.

Covers every node label written through this instance or already
present in the database, so a fresh instance can set up an existing
database without first rewriting every record.

##### `agrag.graphdb.base.GraphStore.transaction` \{#agrag-graphdb-base-GraphStore-transaction}

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

- <code>AsyncIterator\[[GraphStoreTransaction](#agrag-graphdb-base-GraphStoreTransaction)\]</code> – An async context manager yielding the transactional handle.

##### `agrag.graphdb.base.GraphStore.upsert_nodes` \{#agrag-graphdb-base-GraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

**Parameters:**

- **label** (<code>str</code>) – The label this batch is tracked under for constraint and
  index bookkeeping.
- **nodes** (<code>Sequence\[[NodeRecord](common.md#agrag-common-data_models-graph_record-NodeRecord)\]</code>) – The node records to upsert. Each node's `NodeRecord.labels`
  names the full label set actually written to it, which may
  include labels beyond `label`.
- **batch_size** (<code>int</code>) – Records per backend write call, applied within each
  distinct label set when `nodes` mixes more than one. Must
  be positive.

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

##### `agrag.graphdb.base.GraphStore.upsert_relations` \{#agrag-graphdb-base-GraphStore-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>Sequence\[[RelationRecord](common.md#agrag-common-data_models-graph_record-RelationRecord)\]</code>) – The relation records to upsert.
- **batch_size** (<code>int</code>) – Records per backend write call. Must be positive.

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

##### `agrag.graphdb.base.GraphStore.vector_search` \{#agrag-graphdb-base-GraphStore-vector_search}

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

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

#### `agrag.graphdb.base.GraphStoreTransaction` \{#agrag-graphdb-base-GraphStoreTransaction}

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

##### `agrag.graphdb.base.GraphStoreTransaction.execute_read` \{#agrag-graphdb-base-GraphStoreTransaction-execute_read}

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read inside the surrounding transaction.

##### `agrag.graphdb.base.GraphStoreTransaction.execute_write` \{#agrag-graphdb-base-GraphStoreTransaction-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write inside the surrounding transaction.

##### `agrag.graphdb.base.GraphStoreTransaction.upsert_nodes` \{#agrag-graphdb-base-GraphStoreTransaction-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult | None
```

Write or merge nodes inside the surrounding transaction.

##### `agrag.graphdb.base.GraphStoreTransaction.upsert_relations` \{#agrag-graphdb-base-GraphStoreTransaction-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult | None
```

Write or merge relationships inside the surrounding transaction.

### `agrag.graphdb.build_graph_store` \{#agrag-graphdb-build_graph_store}

```python
build_graph_store(value:GraphStoreName | GraphStore, *, tracer:Tracer | None = None) -> GraphStore
```

Build a graph store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>[GraphStoreName](#agrag-graphdb-GraphStoreName) | [GraphStore](#agrag-graphdb-base-GraphStore)</code>) – `"neo4j"`, or an already-constructed `GraphStore`.
- **tracer** (<code>Tracer | None</code>) – Passed to the newly-built store. Not valid together with an
  already-constructed `value` -- that instance's tracer, if any,
  was already fixed at its own construction.

**Returns:**

- <code>[GraphStore](#agrag-graphdb-base-GraphStore)</code> – A ready-to-use graph store.

**Raises:**

- <code>ValueError</code> – `tracer` is given together with an already-constructed
  `value`.

### `agrag.graphdb.entities` \{#agrag-graphdb-entities}

Load persisted entities by id.

**Functions:**

- [**load_entities**](#agrag-graphdb-entities-load_entities) – Load the committed entities stored under the given ids.

**Attributes:**

- [**LOAD_BATCH_SIZE**](#agrag-graphdb-entities-LOAD_BATCH_SIZE) –

#### `agrag.graphdb.entities.LOAD_BATCH_SIZE` \{#agrag-graphdb-entities-LOAD_BATCH_SIZE}

```python
LOAD_BATCH_SIZE = 1000
```

#### `agrag.graphdb.entities.load_entities` \{#agrag-graphdb-entities-load_entities}

```python
load_entities(graph_store:GraphStore, ids:Sequence[UUID], *, tracer:Tracer | None = None) -> dict[UUID, Entity]
```

Load the committed entities stored under the given ids.

Reads in batches of `LOAD_BATCH_SIZE`. Entities that an in-flight
Cutover Job wrote are not returned.

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag-graphdb-base-GraphStore)</code>) – Where the entities live.
- **ids** (<code>Sequence\[UUID\]</code>) – The entity ids to load. Duplicates are read once.
- **tracer** (<code>Tracer | None</code>) – Opens the loading span. None opens no recorded span.

**Returns:**

- <code>dict\[UUID, [Entity](common.md#agrag-common-data_models-entity-Entity)\]</code> – The entities by id. An id with no committed entity is absent from the
- <code>dict\[UUID, [Entity](common.md#agrag-common-data_models-entity-Entity)\]</code> – result, so the caller decides whether that is an error.

**Raises:**

- <code>ValueError</code> – A stored node under a requested id cannot be parsed into
  an entity.
- <code>Exception</code> – Whatever `graph_store` raised while reading.

### `agrag.graphdb.errors` \{#agrag-graphdb-errors}

Errors that the graph-store layer raises.

**Classes:**

- [**GraphStoreAliasConflictError**](#agrag-graphdb-errors-GraphStoreAliasConflictError) – A merge-key alias a merge tried to claim already names another entity.
- [**GraphStoreConstraintViolationError**](#agrag-graphdb-errors-GraphStoreConstraintViolationError) – A write violated a uniqueness constraint the backend enforces.
- [**GraphStoreError**](#agrag-graphdb-errors-GraphStoreError) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](#agrag-graphdb-errors-GraphStoreMissingExtraError) – A graph store exists, but its package extra is not installed.

#### `agrag.graphdb.errors.GraphStoreAliasConflictError` \{#agrag-graphdb-errors-GraphStoreAliasConflictError}

```python
GraphStoreAliasConflictError(conflicts:dict[str, str]) -> None
```

Bases: <code>[GraphStoreConstraintViolationError](#agrag-graphdb-errors-GraphStoreConstraintViolationError)</code>

A merge-key alias a merge tried to claim already names another entity.

Unlike the base class, this is not surfaced by the backend's own
uniqueness constraint -- claiming an already-owned alias is a silent
no-op at the database level (see `upsert_merge_alias_query`) -- so
`apply_merge` detects it itself from the claim's own return rows and
raises this instead. For example, one writer creates a canonical entity
named "Bob" while a concurrent writer separately resolves "Bob" as an
accepted alias of a different canonical entity named "Robert": neither
writer's own node merge_key collides, so recovery must come from here,
not from a constraint violation.

**Attributes:**

- [**conflicts**](#agrag-graphdb-errors-GraphStoreAliasConflictError-conflicts) – Every accepted merge_key this claim found already owned,
  mapped to the entity id that owns it.

##### `agrag.graphdb.errors.GraphStoreAliasConflictError.conflicts` \{#agrag-graphdb-errors-GraphStoreAliasConflictError-conflicts}

```python
conflicts = conflicts
```

#### `agrag.graphdb.errors.GraphStoreConstraintViolationError` \{#agrag-graphdb-errors-GraphStoreConstraintViolationError}

Bases: <code>[GraphStoreError](#agrag-graphdb-errors-GraphStoreError)</code>

A write violated a uniqueness constraint the backend enforces.

Raised instead of letting the backend's own driver exception propagate,
so callers can recognize this specific case -- for example, two
concurrent writers both missing an exact-match lookup and racing to
create the same `merge_key` -- and recover by re-resolving to
whichever write landed first, rather than treating it as a fatal error.

#### `agrag.graphdb.errors.GraphStoreError` \{#agrag-graphdb-errors-GraphStoreError}

Bases: <code>Exception</code>

The base class for every graph-store error.

#### `agrag.graphdb.errors.GraphStoreMissingExtraError` \{#agrag-graphdb-errors-GraphStoreMissingExtraError}

```python
GraphStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[GraphStoreError](#agrag-graphdb-errors-GraphStoreError)</code>

A graph store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-graphdb-errors-GraphStoreMissingExtraError-extra) – The name of the package extra to install.

##### `agrag.graphdb.errors.GraphStoreMissingExtraError.extra` \{#agrag-graphdb-errors-GraphStoreMissingExtraError-extra}

```python
extra = extra
```

### `agrag.graphdb.neo4j` \{#agrag-graphdb-neo4j}

Neo4j graph-store backend.

**Classes:**

- [**Neo4jGraphStore**](#agrag-graphdb-neo4j-Neo4jGraphStore) – A `GraphStore` backed by Neo4j, using native vector indexes.

#### `agrag.graphdb.neo4j.Neo4jGraphStore` \{#agrag-graphdb-neo4j-Neo4jGraphStore}

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[GraphStore](#agrag-graphdb-base-GraphStore)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop.

**Functions:**

- [**close**](#agrag-graphdb-neo4j-Neo4jGraphStore-close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag-graphdb-neo4j-Neo4jGraphStore-connect) – Open the driver and verify connectivity.
- [**ensure_relation_constraint**](#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_relation_constraint) – Create a relationship type's `id` uniqueness constraint once.
- [**ensure_vector_index**](#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag-graphdb-neo4j-Neo4jGraphStore-execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag-graphdb-neo4j-Neo4jGraphStore-execute_write) – Run a write transaction and return its rows.
- [**register_labels**](#agrag-graphdb-neo4j-Neo4jGraphStore-register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag-graphdb-neo4j-Neo4jGraphStore-register_relation_types) – Add types to this instance's known-relation-type set.
- [**session**](#agrag-graphdb-neo4j-Neo4jGraphStore-session) – Open a session to the configured database.
- [**setup_constraints**](#agrag-graphdb-neo4j-Neo4jGraphStore-setup_constraints) – Create `id` and `merge_key` uniqueness constraints per label.
- [**setup_indexes**](#agrag-graphdb-neo4j-Neo4jGraphStore-setup_indexes) – Set up indexes now provided by the store's uniqueness constraints.
- [**transaction**](#agrag-graphdb-neo4j-Neo4jGraphStore-transaction) – Open one Neo4j explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag-graphdb-neo4j-Neo4jGraphStore-vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](#agrag-graphdb-settings-Neo4jSettings) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>AsyncDriver | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this store's methods produce.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.close` \{#agrag-graphdb-neo4j-Neo4jGraphStore-close}

```python
close() -> None
```

Close the driver, releasing its connection pool.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.connect` \{#agrag-graphdb-neo4j-Neo4jGraphStore-connect}

```python
connect() -> None
```

Open the driver and verify connectivity.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.ensure_relation_constraint` \{#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_relation_constraint}

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

##### `agrag.graphdb.neo4j.Neo4jGraphStore.ensure_vector_index` \{#agrag-graphdb-neo4j-Neo4jGraphStore-ensure_vector_index}

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

A concurrent creator can commit the same index after this operation
starts. Neo4j reports that race as an equivalent-schema error, which
means the requested index already exists.

**Raises:**

- <code>[EmbeddingDimensionMismatchError](embedding.md#agrag-embedding-errors-EmbeddingDimensionMismatchError)</code> – The index already exists with a
  different dimension than `dimensions`.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.execute_read` \{#agrag-graphdb-neo4j-Neo4jGraphStore-execute_read}

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

##### `agrag.graphdb.neo4j.Neo4jGraphStore.execute_write` \{#agrag-graphdb-neo4j-Neo4jGraphStore-execute_write}

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag-graphdb-errors-GraphStoreConstraintViolationError)</code> – The write violated a uniqueness
  constraint, translated from the driver's own exception so
  callers do not need a hard dependency on it.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.register_labels` \{#agrag-graphdb-neo4j-Neo4jGraphStore-register_labels}

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>Sequence\[str\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>ValueError</code> – Any label is not a safe identifier.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.register_relation_types` \{#agrag-graphdb-neo4j-Neo4jGraphStore-register_relation_types}

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>Sequence\[str\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>ValueError</code> – Any type is not a safe identifier.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.session` \{#agrag-graphdb-neo4j-Neo4jGraphStore-session}

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.setup_constraints` \{#agrag-graphdb-neo4j-Neo4jGraphStore-setup_constraints}

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

##### `agrag.graphdb.neo4j.Neo4jGraphStore.setup_indexes` \{#agrag-graphdb-neo4j-Neo4jGraphStore-setup_indexes}

```python
setup_indexes() -> None
```

Set up indexes now provided by the store's uniqueness constraints.

Kept as a no-op for callers that provision constraints and indexes in
separate steps. Neo4j creates backing indexes for the `id` and
`merge_key` uniqueness constraints, so creating range indexes for
the same properties would conflict with those constraints.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.transaction` \{#agrag-graphdb-neo4j-Neo4jGraphStore-transaction}

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Open one Neo4j explicit transaction spanning multiple writes.

Commits when the `async with` block exits cleanly; rolls back and
re-raises when it raises. The identity constraint is ensured before
opening the transaction, the same way `upsert_nodes` ensures it
before writing, since `_Neo4jTransaction.upsert_nodes` skips that
check to avoid a nested write racing the transaction it belongs to.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag-graphdb-errors-GraphStoreConstraintViolationError)</code> – A write inside the block, or the
  commit itself, violated a uniqueness constraint -- Neo4j
  validates some constraints only at commit time for an
  explicit transaction, so this can surface here even when
  every individual write appeared to succeed.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.upsert_nodes` \{#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_nodes}

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
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

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.upsert_relations` \{#agrag-graphdb-neo4j-Neo4jGraphStore-upsert_relations}

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

Relationship identity is each record's `id`, not its endpoints: see
`upsert_relation_query` for how endpoint changes and same-id
parallel relationships are handled.

**Returns:**

- <code>[UpsertResult](common.md#agrag-common-data_models-graph_record-UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

##### `agrag.graphdb.neo4j.Neo4jGraphStore.vector_search` \{#agrag-graphdb-neo4j-Neo4jGraphStore-vector_search}

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

### `agrag.graphdb.serialize` \{#agrag-graphdb-serialize}

Convert graph records to driver parameters and graph node rows to models.

**Functions:**

- [**node_params**](#agrag-graphdb-serialize-node_params) – Build the `$records` entry for a node upsert.
- [**parse_entity_node**](#agrag-graphdb-serialize-parse_entity_node) – Parse one stored entity's property dict into an Entity.
- [**relation_params**](#agrag-graphdb-serialize-relation_params) – Build the `$records` entry for a relationship upsert.

#### `agrag.graphdb.serialize.node_params` \{#agrag-graphdb-serialize-node_params}

```python
node_params(record:NodeRecord) -> dict[str, Any]
```

Build the `$records` entry for a node upsert.

The Cutover Job tag is split out of `properties` into its own key
because the upsert queries apply it with `ON CREATE SET`: a job tags
the nodes it creates, never a node it writes over. Left inside the
applied property map it would be set on existing nodes too, which
would hide a committed node from retrieval for the job's duration and
put it in reach of the job's rollback — and rollback deletes tagged
rows.

**Parameters:**

- **record** (<code>[NodeRecord](common.md#agrag-common-data_models-graph_record-NodeRecord)</code>) – The node record to serialize.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict with `id` (string), `properties` (converted, without
- <code>dict\[str, Any\]</code> – the pending tag), and `pending_job_id` (the tag, or None).

#### `agrag.graphdb.serialize.parse_entity_node` \{#agrag-graphdb-serialize-parse_entity_node}

```python
parse_entity_node(node:object) -> Entity | None
```

Parse one stored entity's property dict into an Entity.

Neo4j rows carry no labels, so the label is the prefix of the node's
`merge_key`.

**Parameters:**

- **node** (<code>object</code>) – The node's properties, as a `RETURN n` row holds them.

**Returns:**

- <code>[Entity](common.md#agrag-common-data_models-entity-Entity) | None</code> – The entity, or `None` when `node` is not a property dict or has no
- <code>[Entity](common.md#agrag-common-data_models-entity-Entity) | None</code> – usable `id` or `merge_key`.

#### `agrag.graphdb.serialize.relation_params` \{#agrag-graphdb-serialize-relation_params}

```python
relation_params(record:RelationRecord) -> dict[str, Any]
```

Build the `$records` entry for a relationship upsert.

The Cutover Job tag is split out of `properties` for the same reason
as in :func:`node_params`: only an edge the job creates carries it.

**Parameters:**

- **record** (<code>[RelationRecord](common.md#agrag-common-data_models-graph_record-RelationRecord)</code>) – The relation record to serialize.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict with `id`, `start_id`, `end_id`, `properties`
- <code>dict\[str, Any\]</code> – (converted, without the pending tag), and `pending_job_id` (the
- <code>dict\[str, Any\]</code> – tag, or None).

### `agrag.graphdb.settings` \{#agrag-graphdb-settings}

Settings for the Neo4j graph-store backend.

**Classes:**

- [**Neo4jSettings**](#agrag-graphdb-settings-Neo4jSettings) – Neo4j connection configuration.

#### `agrag.graphdb.settings.Neo4jSettings` \{#agrag-graphdb-settings-Neo4jSettings}

Bases: <code>BaseSettings</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag-graphdb-settings-Neo4jSettings-uri) (<code>str</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag-graphdb-settings-Neo4jSettings-username) (<code>str</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag-graphdb-settings-Neo4jSettings-password) (<code>SecretStr</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag-graphdb-settings-Neo4jSettings-database) (<code>str</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag-graphdb-settings-Neo4jSettings-max_connection_lifetime) (<code>int</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

**Raises:**

- <code>ValueError</code> – `uri` is plaintext (`bolt://` or `neo4j://`) and
  points at a non-local host. Neo4j always authenticates with a
  password, so a plaintext scheme always sends it in the clear; use
  `neo4j+s://` (or `bolt+s://`) for a remote instance.

##### `agrag.graphdb.settings.Neo4jSettings.database` \{#agrag-graphdb-settings-Neo4jSettings-database}

```python
database: str = 'neo4j'
```

##### `agrag.graphdb.settings.Neo4jSettings.max_connection_lifetime` \{#agrag-graphdb-settings-Neo4jSettings-max_connection_lifetime}

```python
max_connection_lifetime: int = 240
```

##### `agrag.graphdb.settings.Neo4jSettings.model_config` \{#agrag-graphdb-settings-Neo4jSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.graphdb.settings.Neo4jSettings.password` \{#agrag-graphdb-settings-Neo4jSettings-password}

```python
password: SecretStr = SecretStr('neo4j')
```

##### `agrag.graphdb.settings.Neo4jSettings.uri` \{#agrag-graphdb-settings-Neo4jSettings-uri}

```python
uri: str = 'bolt://localhost:7687'
```

##### `agrag.graphdb.settings.Neo4jSettings.username` \{#agrag-graphdb-settings-Neo4jSettings-username}

```python
username: str = 'neo4j'
```
