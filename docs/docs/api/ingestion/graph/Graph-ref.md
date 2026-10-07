---
title: agrag.ingestion.graph.Graph
sidebar_label: Graph
---

# `agrag.ingestion.graph.Graph` \{#agrag-ingestion-graph-Graph}

```python
Graph(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None, cutover_settings:CutoverJobSettings | None = None, chunking:Chunking = DEFAULT_CHUNKING, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> None
```

A knowledge graph that a caller can open and add content to.

When an optional VectorStore is configured, every embedding this
graph writes to graph_store is also upserted there, so SearchEngine's
VectorStore path finds the same vectors the GraphStore-native path
does. Collections follow RetrievalSettings' names and are provisioned
by `open()` when missing.

**Functions:**

- [**add**](#agrag-ingestion-graph-Graph-add) – Add content to the graph.
- [**consolidate**](#agrag-ingestion-graph-Graph-consolidate) – Run non-destructive resolution against every persisted raw entity.
- [**deactivate_match**](#agrag-ingestion-graph-Graph-deactivate_match) – Deactivate a semantic match and synchronize replacement retrieval vectors.
- [**delete_document**](#agrag-ingestion-graph-Graph-delete_document) – Soft-delete a document by closing its current PART_OF edges.
- [**detect_communities**](#agrag-ingestion-graph-Graph-detect_communities) – Detect entity communities via hierarchical Leiden.
- [**open**](#agrag-ingestion-graph-Graph-open) – Open a graph, connecting and fully provisioning graph_store.
- [**reevaluate**](#agrag-ingestion-graph-Graph-reevaluate) – Reevaluate matches among the given entities, adding and removing edges.
- [**update**](#agrag-ingestion-graph-Graph-update) – Replace one document version, closing its former PART_OF edges.

**Attributes:**

- [**chunking**](#agrag-ingestion-graph-Graph-chunking) (<code>[Chunking](../../chunking/rules/Chunking.md)</code>) – The rules that pick a chunker for each document.

**Parameters:**

- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](../extract/Extractor.md)</code>) – Runs against each chunk.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Optional second write target for embeddings. When
  set, every embedding the pipeline writes to graph_store is
  also upserted here, so SearchEngine's VectorStore path finds
  the same vectors the GraphStore-native path does. Also gets
  old community vectors removed on each
  detect_communities(apply=True) cycle.
- **retrieval_settings** (<code>[RetrievalSettings](../../retrieval/settings/RetrievalSettings.md) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults. Ignored when
  vector_store is None.
- **cutover_settings** (<code>[CutoverJobSettings](../settings/CutoverJobSettings.md) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **chunking** (<code>[Chunking](../../chunking/rules/Chunking.md)</code>) – The rules that pick a chunker for each document. The
  default is `DEFAULT_CHUNKING`.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the chunk's
  heading path above its text. The stored text does not change.
  Existing embeddings stay until a document is re-chunked with
  `update()`.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs that resolution sends
  to the LLM for each label. A lower value bounds the number of
  verification calls and leaves more pairs undecided.

## `add` \{#agrag-ingestion-graph-Graph-add}

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[AddResult], None] | None = None, return_chunks:bool = False, read_options:ReadOptions | None = None) -> AddResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>SourcesType | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>str | None</code>) – Raw text to add as one document.
- **documents** (<code>Sequence\[[Document](../../common/data_models/document/Document-ref.md)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](../../loaders/corpus/base/Loader.md) | None</code>) – A loader to use instead of the registry default. It requires
  a single-file `source`. A directory, glob, or list of sources
  raises an error.
- **error_policy** (<code>[ErrorPolicy](../../loaders/corpus/types/ErrorPolicy.md)</code>) – The action to take on a per-source error.
- **on_progress** (<code>Callable\[\[[AddResult](../reports/add_result/AddResult.md)\], None\] | None</code>) – A callback the call runs after each batch and once more
  at the end with the fully-populated result.
- **return_chunks** (<code>bool</code>) – Whether to include the produced chunks in the
  returned AddResult. False by default to avoid holding full text
  for a large corpus when not needed.
- **read_options** (<code>[ReadOptions](../../loaders/corpus/types/ReadOptions.md) | None</code>) – How loaders read sources, including the normalization of
  decoded text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[AddResult](../reports/add_result/AddResult.md)</code> – A summary of what was added per pipeline stage. Resolution runs
  automatically: exact identity plus fuzzy, embedding, and
  capped LLM zones over one combined mention list, with
  confirmed matches persisted as MATCHES edges and derived
  ResolvedEntity nodes. LLM verification calls stay bounded
  at ceil(L * MAX_LLM_PAIRS / 10) requests for L labels;
  inspect result.resolution.ambiguous_count for the pairs no
  tier could decide.

**Raises:**

- <code>ValueError</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>UnsupportedFormatError</code> – No loader is registered for a source's format.
- <code>MissingExtraError</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.
- <code>ValueError</code> – The input contains multiple documents with the same
  `document_key`.

## `chunking` \{#agrag-ingestion-graph-Graph-chunking}

```python
chunking: Chunking
```

The rules that pick a chunker for each document.

## `consolidate` \{#agrag-ingestion-graph-Graph-consolidate}

```python
consolidate(*, apply:bool = False) -> ConsolidationReport
```

Run non-destructive resolution against every persisted raw entity.

Dry-run by default: produces matches before any node is touched. Pass
apply=True to write MATCHES edges and derived ResolvedEntity nodes.

For each EntityType label in self.\_schema, fetches every persisted
entity with that label, bounds the pairs actually compared with
GraphCandidateSource's ANN-backed persisted_candidate_indices, and
runs the same zone-routed resolution add() uses (exact, fuzzy
fast-path, embedding similarity, capped LLM review) over those
candidate pairs. Confirmed non-exact matches preserve both raw
Entity nodes and their relationships.

LLM verification calls stay bounded: at most
ceil(L * MAX_LLM_PAIRS / 10) requests for L labels. See Graph.add.

**Parameters:**

- **apply** (<code>bool</code>) – Write the confirmed matches and rebuild resolved entities.
  False produces a report only.

A failed read of an entity's candidates does not stop the pass. That
entity is not compared in this call and the report lists the failure.

**Returns:**

- <code>[ConsolidationReport](../reports/consolidation_report/ConsolidationReport.md)</code> – A report of every confirmed non-exact match, applied or not,
  plus the count of uncertain LLM verdicts and every failure.

## `deactivate_match` \{#agrag-ingestion-graph-Graph-deactivate_match}

```python
deactivate_match(match_id:UUID) -> list[ResolvedEntity]
```

Deactivate a semantic match and synchronize replacement retrieval vectors.

## `delete_document` \{#agrag-ingestion-graph-Graph-delete_document}

```python
delete_document(document_key:str) -> UpdateResult
```

Soft-delete a document by closing its current PART_OF edges.

Currency is read transitively through `PART_OF`: closing the
open edges removes the document from retrieval while its chunks,
the `Document` node, and contributed entities stay in the graph
for provenance. An unknown `document_key` is a no-op. Entities
mentioned only by this document's chunks lose their last evidence
and are pruned with their shrunken clusters. The close and the
prune run as one job's commit and cleanup, so a crash either
leaves the document untouched or completes the deletion.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to delete.

**Returns:**

- <code>[UpdateResult](../reports/update_result/UpdateResult.md)</code> – The deletion summary: `no_op=True` when nothing was stored
  under the key, otherwise `chunks_closed` with
  `new_content_hash=None` and no `add_result`.

<details open>
<summary>Note</summary>

The close-only degenerate case of `Graph.update()`. Both
call into the same shared document-lifecycle helpers. See
`Graph.add()` for the shared ingestion behavior.

</details>

## `detect_communities` \{#agrag-ingestion-graph-Graph-detect_communities}

```python
detect_communities(*, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Dry-run by default. It produces a report of the communities that the
call will write before any node is touched. Pass apply=True to write
them.

Fetches every live domain relation across the whole graph (not scoped
by entity label the way consolidate() is. Community structure spans
entity types), builds a weighted edge list, and runs hierarchical
Leiden off the event loop. Every prior run's Community nodes and
MEMBER_OF edges are deleted before the new ones are written when
apply=True. This is a full recompute, not an incremental update,
so there is no notion of merging this run's output with a
previous one.

**Parameters:**

- **apply** (<code>bool</code>) – Write the computed communities. False produces a report only.
- **max_cluster_size** (<code>int</code>) – Forwarded to compute_communities.
- **resolution** (<code>float</code>) – Forwarded to compute_communities.
- **seed** (<code>int | None</code>) – Forwarded to compute_communities.

**Returns:**

- <code>[CommunityDetectionReport](../reports/community_detection_report/CommunityDetectionReport.md)</code> – A report of every community this call found, applied or not.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](../community/CommunityDetectionMissingExtraError.md)</code> –
  graspologic-native is not installed.

## `open` \{#agrag-ingestion-graph-Graph-open}

```python
open(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None, cutover_settings:CutoverJobSettings | None = None, chunking:Chunking = DEFAULT_CHUNKING, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> Graph
```

Open a graph, connecting and fully provisioning graph_store.

Provisioning order: connect, then register every label/relation type
this graph will ever write (schema's own labels/types plus the fixed
system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
setup_constraints(), then setup_indexes(), then vector indexes for
every schema entity label — so a brand-new database is fully ready,
including the merge_key uniqueness constraints the global exact-match
tier relies on and the embedding vector indexes native search needs,
before this call returns. When vector_store is set, the entity, chunk,
and community collections are provisioned there too (created when
missing) so the dual writes never hit an absent collection.

**Parameters:**

- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](../extract/Extractor.md)</code>) – Runs against each chunk.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Optional second write target for embeddings. See
  __init__.
- **retrieval_settings** (<code>[RetrievalSettings](../../retrieval/settings/RetrievalSettings.md) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults.
- **cutover_settings** (<code>[CutoverJobSettings](../settings/CutoverJobSettings.md) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **chunking** (<code>[Chunking](../../chunking/rules/Chunking.md)</code>) – The rules that pick a chunker for each document; see
  __init__.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the heading path;
  see __init__.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs sent to the LLM for each
  label during resolution; see __init__.

**Returns:**

- <code>Graph</code> – A graph connected to graph_store and ready to accept add() calls.

**Raises:**

- <code>EmbeddingDimensionMismatchError</code> – A vector index in graph_store
  already exists with a different dimension than the embedder
  produces.
- <code>CollectionDimensionMismatchError</code> – A vector_store collection
  already exists with a different dimension than the embedder
  produces.
- <code>Exception</code> – Whatever connect(), registration, constraint/index
  setup, or vector-index provisioning raises. graph_store is
  closed first, so a failed open() never leaks a connection.

## `reevaluate` \{#agrag-ingestion-graph-Graph-reevaluate}

```python
reevaluate(entity_ids:list[UUID]) -> ReevaluationReport
```

Reevaluate matches among the given entities, adding and removing edges.

Fetches exactly the supplied entities, compares same-label pairs
only among this set through one zone-routed Resolver pass, writes
confirmed matches that lack an active edge, and deactivates active
edges among the set the resolver did not confirm. Exact-text pairs
never gain or lose edges. Nothing outside the input set is compared
or touched, and nothing calls this automatically.

LLM verification calls stay bounded at ceil(L * MAX_LLM_PAIRS / 10)
requests for L labels, as in Graph.add.

**Parameters:**

- **entity_ids** (<code>list\[UUID\]</code>) – The persisted entities to reevaluate, deduped with
  input order preserved.

**Returns:**

- <code>[ReevaluationReport](../reports/reevaluation_report/ReevaluationReport.md)</code> – Which entities were reevaluated, which matches were added,
  which match edges were deactivated, and how many inputs had no
  incident added or removed edge.

**Raises:**

- <code>ValueError</code> – An id has no live persisted entity.

## `update` \{#agrag-ingestion-graph-Graph-update}

```python
update(document_key:str, *, text:str | None = None, source:SourcesType | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, read_options:ReadOptions | None = None) -> UpdateResult
```

Replace one document version, closing its former PART_OF edges.

Looks up the persisted `Document` node by `document_key`. An
unchanged content hash is a no-op returning before any chunking,
extraction, or writes, unless the chunker that this graph's rules pick
for the document differs from the one that made its current chunks. A
chunker with new settings re-chunks the document as a content change
does. Chunks written before chunkers were recorded count as unchanged.
Otherwise the fresh content ingests under a Cutover Job holding this
document's lease, and the commit flips the job, closes the document's
open `PART_OF` edges, and clears every pending tag in one
transaction — so a crash either leaves
the old version untouched or completes the replacement including
cleanup. Entities that lose their last evidence are pruned after
the commit, so replacement mentions count as evidence. A source
must resolve to exactly one document.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to replace.
- **text** (<code>str | None</code>) – Replacement text, exactly one of `text`/`source`.
- **source** (<code>SourcesType | None</code>) – A single-file source, glob, or path list resolving to
  exactly one document.
- **loader** (<code>[Loader](../../loaders/corpus/base/Loader.md) | None</code>) – A loader override for a single-file `source`.
- **error_policy** (<code>[ErrorPolicy](../../loaders/corpus/types/ErrorPolicy.md)</code>) – RAISE propagates a stage failure. Any other
  policy records it and continues.
- **read_options** (<code>[ReadOptions](../../loaders/corpus/types/ReadOptions.md) | None</code>) – How loaders read the replacement, including the
  normalization of its text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[UpdateResult](../reports/update_result/UpdateResult.md)</code> – The update summary. A no-op reports `no_op=True` with no
  `add_result`. A change reports `chunks_closed` plus the
  fresh ingestion's `add_result`. An unknown `document_key`
  ingests fresh with `previous_content_hash=None` and
  `chunks_closed=0`.

**Raises:**

- <code>ValueError</code> – Both or neither of `text` and `source` are given, a loader
  override targets multiple sources, or a source resolves to any number
  of documents other than one.

<details open>
<summary>Note</summary>

The fresh-content path shares `ingest_chunks()` with
`Graph.add()`; both callers observe the same pipeline behavior
for the same input.

</details>
