---
title: agrag.ingestion.graph.Graph
sidebar_label: Graph
---

# `agrag.ingestion.graph.Graph` \{#agrag-ingestion-graph-Graph}

```python
Graph(*, schema:SchemaSource, graph_store:GraphStore, embedder:Embedder, extractor:Extractor | None = None, tracer:Tracer | None = None, cutover_settings:CutoverJobSettings | None = None, extraction_settings:ExtractionSettings | None = None, llm_extractor:LLMExtractor | None = None, chunker:Chunker | None = None, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> None
```

A knowledge graph that a caller can open and add content to.

**Functions:**

- [**add**](#agrag-ingestion-graph-Graph-add) – Add content to the graph.
- [**consolidate**](#agrag-ingestion-graph-Graph-consolidate) – Run non-destructive resolution against every persisted raw entity.
- [**convert_candidates**](#agrag-ingestion-graph-Graph-convert_candidates) – Turn approved candidates into graph data after applying their patch.
- [**deactivate_match**](#agrag-ingestion-graph-Graph-deactivate_match) – Deactivate a semantic match and embed the replacement resolved entities.
- [**delete_document**](#agrag-ingestion-graph-Graph-delete_document) – Soft-delete a document by closing its current HAS_PART edges.
- [**detect_communities**](#agrag-ingestion-graph-Graph-detect_communities) – Detect entity communities via hierarchical Leiden.
- [**open**](#agrag-ingestion-graph-Graph-open) – Open a graph, connecting and fully provisioning graph_store.
- [**purge_document**](#agrag-ingestion-graph-Graph-purge_document) – Hard-delete every stored version of a document and its evidence.
- [**reevaluate**](#agrag-ingestion-graph-Graph-reevaluate) – Reevaluate matches among the given entities.
- [**source_status**](#agrag-ingestion-graph-Graph-source_status) – Read a source's version, job lease and discovery index state.
- [**update**](#agrag-ingestion-graph-Graph-update) – Replace one document version, or re-extract it in place.

**Attributes:**

- [**chunker**](#agrag-ingestion-graph-Graph-chunker) (<code>[Chunker](../../chunking/chunker/Chunker-ref.md)</code>) – The chunker that splits every document.
- [**effective_mode**](#agrag-ingestion-graph-Graph-effective_mode) (<code>Literal['gliner', 'hybrid', 'llm']</code>) – The extraction mode this graph uses.
- [**extraction_settings**](#agrag-ingestion-graph-Graph-extraction_settings) –
- [**llm_extractor**](#agrag-ingestion-graph-Graph-llm_extractor) (<code>[LLMExtractor](../extract/LLMExtractor.md) | None</code>) – The LLM slot, whether injected or built from environment settings.
- [**llm_model_name**](#agrag-ingestion-graph-Graph-llm_model_name) (<code>str | None</code>) – The model name of the LLM slot, or None when it is unset.

**Parameters:**

- **schema** (<code>[SchemaSource](../../schema/loader/SchemaSource.md)</code>) – The schema the extractor receives. A `GraphSchema` is
  used as given. Any other value goes through `load_schema`: a
  `Preset`, a shipped name (`"default"`, `"operations"` or
  `"legal"`), a file path, a dict, a list of strings, a Pydantic
  class, or JSON text. Raises `SchemaLoadError` when the
  value is not a valid schema.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](../extract/Extractor.md) | None</code>) – The local extraction slot, used in `gliner` and
  `hybrid` modes.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **cutover_settings** (<code>[CutoverJobSettings](../settings/CutoverJobSettings.md) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **extraction_settings** (<code>[ExtractionSettings](../settings/ExtractionSettings.md) | None</code>) – The extraction settings this graph uses.
  None uses settings from a GLiNER extractor, or
  the ExtractionSettings defaults. Pass the same object to both.
- **llm_extractor** (<code>[LLMExtractor](../extract/LLMExtractor.md) | None</code>) – The LLM slot used in `hybrid` and `llm` modes.
  None builds a BAMLExtractor when LLM settings are configured.
- **chunker** (<code>[Chunker](../../chunking/chunker/Chunker-ref.md) | None</code>) – The chunker that splits every document. None uses
  `Chunker()`.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the chunk's
  heading path above its text. The stored text does not change.
  Existing embeddings stay until a document is re-chunked with
  `update()`.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs that resolution sends
  to the LLM for each label. A lower value bounds the number of
  verification calls and leaves more pairs undecided. Zero sends
  no pairs to the LLM.

## `add` \{#agrag-ingestion-graph-Graph-add}

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[AddResult], None] | None = None, return_chunks:bool = False, read_options:ReadOptions | None = None) -> AddResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

A key that already has a current version is handled as `update`
handles it. Content that matches the stored version is skipped and
counted in `ingestion.unchanged`, and changed content replaces the
current version. A key without a current
version, such as a new key or a deleted document, is added as a new
document. Calling `add` again with the same documents therefore writes
only what changed.

If an extraction fails for a chunk, the document and its chunks are
written without the extraction stamp, so the next `update` extracts
them again instead of returning a no-op.

**Parameters:**

- **source** (<code>SourcesType | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>str | None</code>) – Raw text to add as one document.
- **documents** (<code>Sequence\[[Document](../../common/data_models/document/Document-ref.md)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](../../loaders/base/Loader.md) | None</code>) – A loader to use instead of the registry default. It requires
  a single-file `source`. A directory, glob, or list of sources
  raises an error.
- **error_policy** (<code>[ErrorPolicy](../../loaders/types/ErrorPolicy.md)</code>) – The action to take on a per-source error.
- **on_progress** (<code>Callable\[\[[AddResult](../reports/add_result/AddResult.md)\], None\] | None</code>) – A callback the call runs after each batch and once more
  at the end with the fully-populated result.
- **return_chunks** (<code>bool</code>) – Whether to include the produced chunks in the
  returned AddResult. False by default to avoid holding full text
  for a large corpus when not needed. Chunks of a document that
  is updated instead of added are not included.
- **read_options** (<code>[ReadOptions](../../loaders/types/ReadOptions.md) | None</code>) – How loaders read sources, including the normalization of
  decoded text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[AddResult](../reports/add_result/AddResult.md)</code> – A summary of what was added per pipeline stage. Resolution runs
  automatically: exact identity plus fuzzy, embedding, and
  capped LLM zones over one combined mention list, with
  confirmed matches persisted as MATCHES edges and derived
  ResolvedEntity nodes. LLM verification calls stay bounded
  at ceil(L * MAX_LLM_PAIRS / 10) requests for L labels;
  within each label, the highest-similarity pairs are verified
  first. Inspect result.resolution.ambiguous_count for uncertain
  model verdicts. `failed_llm_requests` counts requests that
  raised, `cap_truncated_pairs` counts ambiguous pairs over
  the per-label cap, and `llm_unavailable_pairs` counts
  ambiguous pairs skipped because LLM settings or a comparator
  were unavailable.
  These pairs stay undecided. `in_batch_groups` counts only
  groups with at least two mentions from this batch.
  `escalation` counts the chunks the LLM extractor read in this
  call. The call logs that report at INFO when an LLM extractor
  is set.

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

## `chunker` \{#agrag-ingestion-graph-Graph-chunker}

```python
chunker: Chunker
```

The chunker that splits every document.

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
ceil(L * MAX_LLM_PAIRS / 10) requests for L labels, as in Graph.add.
Within a label, the highest-similarity pairs are verified first.

**Parameters:**

- **apply** (<code>bool</code>) – Write the confirmed matches and rebuild resolved entities.
  False produces a report only.

A failed read of an entity's candidates does not stop the pass. That
entity is not compared in this call and the report lists the failure.

**Returns:**

- <code>[ConsolidationReport](../reports/consolidation_report/ConsolidationReport.md)</code> – A report of every confirmed non-exact match, applied or not,
  plus the count of uncertain LLM verdicts, failed LLM requests,
  pairs over the per-label cap, pairs skipped because LLM
  settings were missing, and every other failure.

## `convert_candidates` \{#agrag-ingestion-graph-Graph-convert_candidates}

```python
convert_candidates(patch:SchemaPatch | Path, *, error_policy:ErrorPolicy = ErrorPolicy.RAISE) -> ConversionReport
```

Turn approved candidates into graph data after applying their patch.

The graph must use the updated schema. Entity candidates become entity
nodes in place or fold into an exact-name owner. Relation and property
candidates become graph data. Graph writes are atomic; repeated calls
skip candidates already converted.

**Parameters:**

- **patch** (<code>[SchemaPatch](../../common/data_models/candidate_review/SchemaPatch.md) | Path</code>) – The schema patch, or its JSON file path.
- **error_policy** (<code>[ErrorPolicy](../../loaders/types/ErrorPolicy.md)</code>) – How to report description embedding failures that
  occur after the graph transaction commits.

**Returns:**

- <code>[ConversionReport](../reports/conversion_report/ConversionReport.md)</code> – Counts of converted data and reasons for skipped candidates.

**Raises:**

- <code>PatchNotAppliedError</code> – The active schema does not include the patch.

## `deactivate_match` \{#agrag-ingestion-graph-Graph-deactivate_match}

```python
deactivate_match(match_id:UUID) -> list[ResolvedEntity]
```

Deactivate a semantic match and embed the replacement resolved entities.

**Raises:**

- <code>ValueError</code> – The match does not exist or an in-flight job has not
  committed it.

## `delete_document` \{#agrag-ingestion-graph-Graph-delete_document}

```python
delete_document(document_key:str) -> UpdateResult
```

Soft-delete a document by closing its current HAS_PART edges.

Currency is read transitively through `HAS_PART`: closing the
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
  under the key, otherwise `parts_closed` with
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
by entity label the way consolidate() is; community structure spans
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

## `effective_mode` \{#agrag-ingestion-graph-Graph-effective_mode}

```python
effective_mode: Literal['gliner', 'hybrid', 'llm']
```

The extraction mode this graph uses.

## `extraction_settings` \{#agrag-ingestion-graph-Graph-extraction_settings}

```python
extraction_settings = settings
```

## `llm_extractor` \{#agrag-ingestion-graph-Graph-llm_extractor}

```python
llm_extractor: LLMExtractor | None
```

The LLM slot, whether injected or built from environment settings.

## `llm_model_name` \{#agrag-ingestion-graph-Graph-llm_model_name}

```python
llm_model_name: str | None
```

The model name of the LLM slot, or None when it is unset.

## `open` \{#agrag-ingestion-graph-Graph-open}

```python
open(*, schema:SchemaSource, graph_store:GraphStore, embedder:Embedder, extractor:Extractor | None = None, tracer:Tracer | None = None, cutover_settings:CutoverJobSettings | None = None, extraction_settings:ExtractionSettings | None = None, llm_extractor:LLMExtractor | None = None, chunker:Chunker | None = None, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> Graph
```

Open a graph, connecting and fully provisioning graph_store.

Provisioning order: connect, then register every label/relation type
this graph will ever write (schema's own labels/types plus the fixed
system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
setup_constraints(), then setup_indexes(), then vector and full-text
indexes for every schema entity label, then the full-text index on chunk
text. A brand-new database is fully ready,
including the merge_key uniqueness constraints the global exact-match
tier relies on, the embedding vector indexes native search needs, the
entity name indexes that entity discovery reads, and the chunk full-text
index that evidence discovery reads, before this call returns.

**Parameters:**

- **schema** (<code>[SchemaSource](../../schema/loader/SchemaSource.md)</code>) – The schema the extractor receives. A `GraphSchema` is
  used as given. Any other value goes through `load_schema`: a
  `Preset`, a shipped name (`"default"`, `"operations"` or
  `"legal"`), a file path, a dict, a list of strings, a Pydantic
  class, or JSON text. Raises `SchemaLoadError` when the
  value is not a valid schema.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](../extract/Extractor.md) | None</code>) – The local extraction slot, used in `gliner` and
  `hybrid` modes.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **cutover_settings** (<code>[CutoverJobSettings](../settings/CutoverJobSettings.md) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **extraction_settings** (<code>[ExtractionSettings](../settings/ExtractionSettings.md) | None</code>) – Extraction settings for this graph; see
  __init__.
- **llm_extractor** (<code>[LLMExtractor](../extract/LLMExtractor.md) | None</code>) – The LLM slot; see __init__.
- **chunker** (<code>[Chunker](../../chunking/chunker/Chunker-ref.md) | None</code>) – The chunker that splits every document; see __init__.
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
- <code>Exception</code> – Whatever connect(), registration, constraint/index
  setup, or vector-index provisioning raises. graph_store is
  closed first, so a failed open() never leaks a connection.

## `purge_document` \{#agrag-ingestion-graph-Graph-purge_document}

```python
purge_document(document_key:str) -> UpdateResult
```

Hard-delete every stored version of a document and its evidence.

The commit removes the chunk, section, table and figure nodes of every
version. Each relation that cites those chunks in `source_chunk_ids`
drops them, and a relation left with no evidence is deleted, whether or
not a chunk still mentions its endpoints. Pending candidates that cite
the chunks are deleted too. Entities that lose their last evidence, the
ones mentioned by the chunks and the endpoints of the relations they
cited, are pruned after the commit, as for a delete. The Document node
and its activation records stay, and each dependent decision is flagged
`source_removed`. Purging a key that has no stored content is a no-op.

This lives on `Graph` rather than `RetentionMemory`: a purge needs
the graph schema, embedder and cutover settings to clean up, and
`RetentionMemory` covers only project-scoped memory records.

Approved and rejected candidates remain without their removed evidence
links. Community summaries remain until community detection runs again.
Purge scans relationships for chunk citations and deletes content in one
transaction. Preflight rejects more than 10,000 content nodes, cited
relations, pending candidates, or combined mention and citation endpoint
records before starting the cutover job.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to purge.

**Returns:**

- <code>[UpdateResult](../reports/update_result/UpdateResult.md)</code> – The purge summary: `no_op=True` when no content was stored under the
  key, otherwise `parts_closed` with `new_content_hash=None`
  and no `add_result`.

**Raises:**

- <code>ValueError</code> – The document exceeds a purge preflight record limit.

## `reevaluate` \{#agrag-ingestion-graph-Graph-reevaluate}

```python
reevaluate(entity_ids:list[UUID]) -> ReevaluationReport
```

Reevaluate matches among the given entities.

Fetches exactly the supplied entities, compares same-label pairs
only among this set through one zone-routed Resolver pass, writes
confirmed matches that lack an active edge, and deactivates active
edges only when the resolver rejects their pair. Exact-text pairs
never gain or lose edges. An active edge is deactivated only when the
resolver rejects its pair: an embedding score under the discard
threshold, or an explicit LLM "no match". When the resolver cannot
decide the pair (the LLM request failed, the pair was over the
per-label cap, no LLM settings were found, or the model answered
uncertain), the edge stays active and its id appears in
`matches_unverified`. Nothing outside the input set is compared or
touched, and nothing calls this automatically.

LLM verification calls stay bounded at ceil(L * MAX_LLM_PAIRS / 10)
requests for L labels, as in Graph.add. Within a label, the
highest-similarity pairs are verified first.

**Parameters:**

- **entity_ids** (<code>list\[UUID\]</code>) – The persisted entities to reevaluate, deduped with
  input order preserved.

**Returns:**

- <code>[ReevaluationReport](../reports/reevaluation_report/ReevaluationReport.md)</code> – Which entities were reevaluated, which matches were added,
  which match edges were deactivated, which were left
  unverified, how many inputs had no incident added or removed
  edge, and the counts of failed LLM requests, pairs over the
  per-label cap, and pairs skipped because LLM settings were
  missing.

**Raises:**

- <code>ValueError</code> – An id has no live persisted entity.

## `source_status` \{#agrag-ingestion-graph-Graph-source_status}

```python
source_status(document_key:str) -> SourceStatus
```

Read a source's version, job lease and discovery index state.

## `update` \{#agrag-ingestion-graph-Graph-update}

```python
update(document_key:str, *, text:str | None = None, source:SourcesType | None = None, document:Document | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, read_options:ReadOptions | None = None, force:bool = False) -> UpdateResult
```

Replace one document version, or re-extract it in place.

Looks up the persisted `Document` node by `document_key`. The update
is a no-op, returning before any chunking, extraction, or writes, only
when the document has an open chunk and the content hash, the chunker
fingerprint, the schema fingerprint, the extraction fingerprint and dates
all equal the stored ones, and `force` is false.
If only the extraction fingerprint differs (a
description, a threshold, or the model name), the document is extracted
again in place. Its chunks stay and are not embedded again. The old
evidence of the document is removed at the commit, and entities that
only the old run produced are removed. If the content, the chunker, or
the schema structure differs, the new version is written. The old
version closes at the commit, and entities that only the old version
produced are removed. If an extraction fails for a chunk, the document is
not stamped current, so the next update extracts it again. An in-place
update keeps the previous evidence of the failed chunk. Chunks written
before the fingerprints were recorded are extracted in place when their
content, chunker, and schema match. A document closed by
`delete_document` has no open chunk, so the same text is added again.
If only `published_at` or `content_date` differs, the two dates are
written and nothing is extracted.

The new version ingests under a Cutover Job holding this document's
lease. The commit flips the job, closes the document's open
`HAS_PART` edges, and clears every pending tag in one transaction, so
a crash either leaves the old version untouched or completes the
replacement including cleanup. Entities that lose their last evidence
are pruned after the commit, so replacement mentions count as evidence.
A source must resolve to exactly one document.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to replace.
- **text** (<code>str | None</code>) – Replacement text. Give exactly one of `text`, `source`, and
  `document`.
- **source** (<code>SourcesType | None</code>) – A single-file source, glob, or path list resolving to
  exactly one document.
- **document** (<code>[Document](../../common/data_models/document/Document-ref.md) | None</code>) – An already-built replacement Document. It skips loading and
  normalization, so its text and `content_hash` are used as given.
  Its `resolved_document_key` must equal `document_key`.
- **loader** (<code>[Loader](../../loaders/base/Loader.md) | None</code>) – A loader override for a single-file `source`.
- **error_policy** (<code>[ErrorPolicy](../../loaders/types/ErrorPolicy.md)</code>) – RAISE propagates a stage failure. Any other
  policy records it and continues. Candidate storage failures
  always abort replacement to preserve committed evidence.
- **read_options** (<code>[ReadOptions](../../loaders/types/ReadOptions.md) | None</code>) – How loaders read the replacement, including the
  normalization of its text. None uses `ReadOptions()` defaults.
- **force** (<code>bool</code>) – Extract the entities again on the same chunks, even when the
  stored values match. Has no effect when the text, the chunker or
  the schema changed, because those already write a new version.

**Returns:**

- <code>[UpdateResult](../reports/update_result/UpdateResult.md)</code> – The update summary. A no-op reports `no_op=True` with no
  `add_result`. A metadata-only update also has no `add_result`
  and reports `parts_closed=0`. The `decision` identifies the
  selected update path. An extraction reports `parts_closed` plus the
  fresh ingestion's `add_result`. An unknown `document_key`
  ingests fresh with `previous_content_hash=None` and
  `parts_closed=0`.

**Raises:**

- <code>ValueError</code> – Other than exactly one of `text`, `source`, and
  `document` is given, a loader override targets multiple sources, a
  source resolves to any number of documents other than one, or the
  `document` key differs from `document_key`.

<details open>
<summary>Note</summary>

The fresh-content path shares `ingest_chunks()` with
`Graph.add()`; both callers observe the same pipeline behavior
for the same input.

</details>
