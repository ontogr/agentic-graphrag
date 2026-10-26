---
title: agrag.ingestion.vector_sync.VectorSync
sidebar_label: VectorSync
---

# `agrag.ingestion.vector_sync.VectorSync` \{#agrag-ingestion-vector_sync-VectorSync}

```python
VectorSync(*, store:VectorStore, embedder:Embedder, graph_store:GraphStore, tracer:Tracer | None = None, embed_heading_path:bool = True) -> None
```

Own guarded embedding, deletion and repair operations for one graph.

**Functions:**

- [**delete_absent**](#agrag-ingestion-vector_sync-VectorSync-delete_absent) – Delete vectors with absent graph nodes and return the removed count.
- [**repair**](#agrag-ingestion-vector_sync-VectorSync-repair) – Restore missing vectors and optionally delete store-only ids.
- [**replace_communities**](#agrag-ingestion-vector_sync-VectorSync-replace_communities) – Upsert replacement community vectors and remove absent old vectors.
- [**sync_committed**](#agrag-ingestion-vector_sync-VectorSync-sync_committed) – Re-embed committed targets from their current graph state.
- [**upsert_owned**](#agrag-ingestion-vector_sync-VectorSync-upsert_owned) – Embed and upsert eligible rows, deferring committed rows in a job.

**Attributes:**

- [**embed_heading_path**](#agrag-ingestion-vector_sync-VectorSync-embed_heading_path) –
- [**embedder**](#agrag-ingestion-vector_sync-VectorSync-embedder) –
- [**graph_store**](#agrag-ingestion-vector_sync-VectorSync-graph_store) –
- [**store**](#agrag-ingestion-vector_sync-VectorSync-store) –
- [**tracer**](#agrag-ingestion-vector_sync-VectorSync-tracer) –

`embed_heading_path` keeps chunk re-syncs consistent with ingestion.

## `delete_absent` \{#agrag-ingestion-vector_sync-VectorSync-delete_absent}

```python
delete_absent(kind:VectorKind, candidate_ids:Sequence[UUID]) -> int
```

Delete vectors with absent graph nodes and return the removed count.

## `embed_heading_path` \{#agrag-ingestion-vector_sync-VectorSync-embed_heading_path}

```python
embed_heading_path = embed_heading_path
```

## `embedder` \{#agrag-ingestion-vector_sync-VectorSync-embedder}

```python
embedder = embedder
```

## `graph_store` \{#agrag-ingestion-vector_sync-VectorSync-graph_store}

```python
graph_store = graph_store
```

## `repair` \{#agrag-ingestion-vector_sync-VectorSync-repair}

```python
repair(kinds:Sequence[VectorKind] | None = None, *, prune:bool = False) -> VectorRepairResult
```

Restore missing vectors and optionally delete store-only ids.

## `replace_communities` \{#agrag-ingestion-vector_sync-VectorSync-replace_communities}

```python
replace_communities(communities:Sequence[Community], *, old_ids:Sequence[UUID]) -> None
```

Upsert replacement community vectors and remove absent old vectors.

## `store` \{#agrag-ingestion-vector_sync-VectorSync-store}

```python
store = store
```

## `sync_committed` \{#agrag-ingestion-vector_sync-VectorSync-sync_committed}

```python
sync_committed(targets:Sequence[VectorTarget]) -> list[StageFailure]
```

Re-embed committed targets from their current graph state.

Missing rows and rows that change during embedding are skipped. A
failure in one batch is returned without preventing later batches.

## `tracer` \{#agrag-ingestion-vector_sync-VectorSync-tracer}

```python
tracer = get_tracer(tracer)
```

## `upsert_owned` \{#agrag-ingestion-vector_sync-VectorSync-upsert_owned}

```python
upsert_owned(kind:VectorKind, items:Sequence[VectorItem], *, job_id:UUID | str | None, deferred:DeferredWrites | None) -> list[UUID]
```

Embed and upsert eligible rows, deferring committed rows in a job.

Rows are rechecked against their graph ownership and embedding text
before embedding. Committed rows reached by a job are recorded for
post-commit synchronization instead of being written early.
