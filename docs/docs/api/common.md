---
title: agrag.common
sidebar_position: 4
---

## `agrag.common` \{#agrag-common}

Common utilities and data models shared across agrag.

**Modules:**

- [**data_models**](#agrag-common-data_models) – Shared data models used by agrag components.
- [**text**](#agrag-common-text) – Shared text normalization used across resolution and merge-key computation.
- [**validation**](#agrag-common-validation) – Validation helpers shared across storage backends.

### `agrag.common.data_models` \{#agrag-common-data_models}

Shared data models used by agrag components.

**Modules:**

- [**chunk**](#agrag-common-data_models-chunk) – The Chunk model: one retrieval-sized piece of a Document.
- [**community**](#agrag-common-data_models-community) – The Community model: a Leiden-detected entity cluster with an LLM report.
- [**cutover_job**](#agrag-common-data_models-cutover_job) – Crash-recoverable state for one add/update/delete_document call.
- [**data_point**](#agrag-common-data_models-data_point) – The base class for a graph node.
- [**document**](#agrag-common-data_models-document) – The Document model: one unit of source text, before chunking.
- [**entity**](#agrag-common-data_models-entity) – A permanent mention-level graph node, accumulated by exact-name matching.
- [**extraction**](#agrag-common-data_models-extraction) – Pre-resolution entity and relation mentions produced by an Extractor.
- [**graph_record**](#agrag-common-data_models-graph_record) – Graph storage record shapes for GraphStore.
- [**graph_schema**](#agrag-common-data_models-graph_schema) – The GraphSchema contract: entity and relation types extraction validates against.
- [**normalization**](#agrag-common-data_models-normalization) – The Normalization model: how a loader turned source bytes into text.
- [**provenance**](#agrag-common-data_models-provenance) – Provenance types for a chunk.
- [**query_value**](#agrag-common-data_models-query_value) – A result row returned by a direct graph query.
- [**relation**](#agrag-common-data_models-relation) – The canonical, deduped graph relationship that merge mechanics produces.
- [**resolved_entity**](#agrag-common-data_models-resolved_entity) – Materialized identity clusters for non-destructive entity resolution.
- [**search_result**](#agrag-common-data_models-search_result) – One retrieved item, tagged with source and relevance score.
- [**stage_failure**](#agrag-common-data_models-stage_failure) – Per-stage failure record and its per-call cap.
- [**vector_record**](#agrag-common-data_models-vector_record) – Vector storage record shapes shared by VectorStore and GraphStore.

**Classes:**

- [**Chunk**](#agrag-common-data_models-Chunk) – One retrieval-sized piece of a Document.
- [**Community**](#agrag-common-data_models-Community) – A cluster of entities detected by hierarchical Leiden, with an LLM report.
- [**Distance**](#agrag-common-data_models-Distance) – A distance metric a vector index compares embeddings with.
- [**Document**](#agrag-common-data_models-Document) – One unit of source text, before chunking.
- [**DocumentFamily**](#agrag-common-data_models-DocumentFamily) – The shape of a document's source.
- [**Entity**](#agrag-common-data_models-Entity) – A permanent mention-level node, never destroyed once written.
- [**EntityType**](#agrag-common-data_models-EntityType) – One kind of entity a schema recognizes.
- [**GraphSchema**](#agrag-common-data_models-GraphSchema) – A versioned contract of entity and relation types.
- [**NodeRecord**](#agrag-common-data_models-NodeRecord) – One graph node, ready to write.
- [**Normalization**](#agrag-common-data_models-Normalization) – How a loader turned source bytes into `Document.text`.
- [**PageProvenance**](#agrag-common-data_models-PageProvenance) – The location of a chunk across one or more pages.
- [**Relation**](#agrag-common-data_models-Relation) – A resolved relationship between two Entity nodes.
- [**RelationRecord**](#agrag-common-data_models-RelationRecord) – One graph relationship, ready to write.
- [**RelationType**](#agrag-common-data_models-RelationType) – One kind of relation a schema recognizes.
- [**ResolvedEntity**](#agrag-common-data_models-ResolvedEntity) – A materialized cluster of entities that refer to the same thing.
- [**SearchResult**](#agrag-common-data_models-SearchResult) – One retrieved item, tagged with where it came from.
- [**SourceFormat**](#agrag-common-data_models-SourceFormat) – A source format that a loader can read.
- [**TextProvenance**](#agrag-common-data_models-TextProvenance) – The location of a chunk inside flattened document text.
- [**VectorRecord**](#agrag-common-data_models-VectorRecord) – One vector and its payload, ready to write to a collection or index.

**Attributes:**

- [**GENERIC**](#agrag-common-data_models-GENERIC) – A ready-made schema for open-domain text.

#### `agrag.common.data_models.Chunk` \{#agrag-common-data_models-Chunk}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

One retrieval-sized piece of a Document.

**Attributes:**

- [**document_id**](#agrag-common-data_models-Chunk-document_id) (<code>UUID</code>) – The id of the persisted Document graph node this chunk
  belongs to (see `Document.node_id_for`). Stable across content
  versions of the same logical document; per-version identity lives
  in `Chunk.id` instead.
- [**index**](#agrag-common-data_models-Chunk-index) (<code>int</code>) – The position of the chunk within its document, from 0.
- [**text**](#agrag-common-data_models-Chunk-text) (<code>str</code>) – The chunk text.
- [**provenance**](#agrag-common-data_models-Chunk-provenance) (<code>[TextProvenance](#agrag-common-data_models-provenance-TextProvenance) | [PageProvenance](#agrag-common-data_models-provenance-PageProvenance)</code>) – The location of this chunk in its source. The shape of this
  value depends on which chunker made the chunk.
- [**heading_path**](#agrag-common-data_models-Chunk-heading_path) (<code>list\[str\]</code>) – The headings that contain this chunk, from outermost to innermost.
  Empty for a docling chunk and for a chunk with no heading above it.
- [**content_kind**](#agrag-common-data_models-Chunk-content_kind) (<code>Literal['text', 'table_row', 'code', 'heading']</code>) – The kind of content in this chunk. A text chunker always sets
  `"text"`. A docling chunk can also be `"table_row"`.
- [**chunker**](#agrag-common-data_models-Chunk-chunker) (<code>str | None</code>) – The strategy name of the chunker that made this chunk. `None` for a
  chunk written before chunkers were recorded.
- [**chunker_hash**](#agrag-common-data_models-Chunk-chunker_hash) (<code>str | None</code>) – The fingerprint of the settings of the chunker that made this
  chunk. `None` for a chunk written before chunkers were recorded.
- [**level**](#agrag-common-data_models-Chunk-level) (<code>int</code>) – `1` for a parent chunk, `0` for every other chunk. A parent
  chunk is the unit of extraction. A child chunk is the unit of search.
- [**parent_id**](#agrag-common-data_models-Chunk-parent_id) (<code>UUID | None</code>) – The id of the parent chunk of a child chunk. `None` for a
  parent and for a chunk that has no parent.

**Functions:**

- [**id_for**](#agrag-common-data_models-Chunk-id_for) – Compute the chunk id.
- [**section_label**](#agrag-common-data_models-Chunk-section_label) – Return the heading path as one line, or `None` when the path is empty.
- [**to_node_record**](#agrag-common-data_models-Chunk-to_node_record) – Return this chunk as a GraphStore write record.

##### `agrag.common.data_models.Chunk.chunker` \{#agrag-common-data_models-Chunk-chunker}

```python
chunker: str | None = None
```

##### `agrag.common.data_models.Chunk.chunker_hash` \{#agrag-common-data_models-Chunk-chunker_hash}

```python
chunker_hash: str | None = None
```

##### `agrag.common.data_models.Chunk.content_kind` \{#agrag-common-data_models-Chunk-content_kind}

```python
content_kind: Literal['text', 'table_row', 'code', 'heading'] = 'text'
```

##### `agrag.common.data_models.Chunk.contextual_text` \{#agrag-common-data_models-Chunk-contextual_text}

```python
contextual_text: str
```

The text with its heading path above it, for embedding.

The stored text and its offsets do not change. A chunk with no heading path
returns its text.

##### `agrag.common.data_models.Chunk.created_at` \{#agrag-common-data_models-Chunk-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

##### `agrag.common.data_models.Chunk.document_id` \{#agrag-common-data_models-Chunk-document_id}

```python
document_id: UUID
```

##### `agrag.common.data_models.Chunk.embedding` \{#agrag-common-data_models-Chunk-embedding}

```python
embedding: list[float] | None = None
```

##### `agrag.common.data_models.Chunk.heading_path` \{#agrag-common-data_models-Chunk-heading_path}

```python
heading_path: list[str] = Field(default_factory=list)
```

##### `agrag.common.data_models.Chunk.id` \{#agrag-common-data_models-Chunk-id}

```python
id: UUID | None = None
```

##### `agrag.common.data_models.Chunk.id_for` \{#agrag-common-data_models-Chunk-id_for}

```python
id_for(*, document_id:UUID, version_id:UUID | None = None, provenance:TextProvenance | PageProvenance, index:int, chunker_hash:str | None = None, level:int = 0) -> UUID
```

Compute the chunk id.

For a text chunk, the id comes from the document id and the character span. A
change in chunk size shifts the span, so it also changes the id. When supplied,
`version_id` makes the id distinct for each version of a document.

For a docling chunk, the id comes from the document id, the chunker hash and
the chunk index instead. The hash keeps a re-chunk with new settings from
overwriting chunk N of the earlier settings. Docling parsing is not always the
same between runs, so this id is not stable across a re-parse of the same
source.

**Parameters:**

- **document_id** (<code>UUID</code>) – The id of the parent Document.
- **version_id** (<code>UUID | None</code>) – Optional id for the parent document version.
- **provenance** (<code>[TextProvenance](#agrag-common-data_models-provenance-TextProvenance) | [PageProvenance](#agrag-common-data_models-provenance-PageProvenance)</code>) – The provenance of the chunk. Its type picks which id rule
  applies.
- **index** (<code>int</code>) – The position of the chunk within its document.
- **chunker_hash** (<code>str | None</code>) – The fingerprint of the chunker. Only a docling chunk uses
  it; a text chunk id ignores it.
- **level** (<code>int</code>) – The chunk level. A parent chunk (level 1) adds a level part, so a
  parent and a child with the same span get different ids. The id of a
  level 0 chunk does not change.

**Returns:**

- <code>UUID</code> – The chunk id.

##### `agrag.common.data_models.Chunk.index` \{#agrag-common-data_models-Chunk-index}

```python
index: int = 0
```

##### `agrag.common.data_models.Chunk.level` \{#agrag-common-data_models-Chunk-level}

```python
level: int = 0
```

##### `agrag.common.data_models.Chunk.metadata` \{#agrag-common-data_models-Chunk-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Chunk.parent_id` \{#agrag-common-data_models-Chunk-parent_id}

```python
parent_id: UUID | None = None
```

##### `agrag.common.data_models.Chunk.provenance` \{#agrag-common-data_models-Chunk-provenance}

```python
provenance: TextProvenance | PageProvenance = Field(discriminator='kind')
```

##### `agrag.common.data_models.Chunk.section_label` \{#agrag-common-data_models-Chunk-section_label}

```python
section_label() -> str | None
```

Return the heading path as one line, or `None` when the path is empty.

Whitespace runs in a heading become one space, and runs of three or more
dashes become one dash, so a heading cannot end the text block of the
extraction prompt.

##### `agrag.common.data_models.Chunk.text` \{#agrag-common-data_models-Chunk-text}

```python
text: str
```

##### `agrag.common.data_models.Chunk.to_node_record` \{#agrag-common-data_models-Chunk-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this chunk as a GraphStore write record.

Provenance is flattened to a plain JSON-safe dict via model_dump —
GraphStore's own serialize.node_params only converts UUIDs and walks
containers.

**Raises:**

- <code>ValueError</code> – id is None.

#### `agrag.common.data_models.Community` \{#agrag-common-data_models-Community}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A cluster of entities detected by hierarchical Leiden, with an LLM report.

**Attributes:**

- [**title**](#agrag-common-data_models-Community-title) (<code>str</code>) – A short, human-readable name for the community.
- [**summary**](#agrag-common-data_models-Community-summary) (<code>str</code>) – A prose summary of what the community is about.
- [**rating**](#agrag-common-data_models-Community-rating) (<code>float</code>) – An importance rating for this community, 0-10.
- [**rating_explanation**](#agrag-common-data_models-Community-rating_explanation) (<code>str</code>) – One sentence explaining the rating.
- [**findings**](#agrag-common-data_models-Community-findings) (<code>list\[str\]</code>) – Distinct factual claims the report supports.
- [**member_ids**](#agrag-common-data_models-Community-member_ids) (<code>list\[UUID\]</code>) – Ids of every Entity in this community, ordered by
  internal weighted degree descending (see compute_communities) --
  the highest-centrality, most representative members first.
- [**internal_weight**](#agrag-common-data_models-Community-internal_weight) (<code>float</code>) – Total weight of edges where both endpoints are
  members of this community. A free-to-compute (no extra query,
  no new dependency) importance signal, used in place of raw
  member count to decide which communities get a real LLM report
  -- a small but densely-attested community can matter more than
  a larger sparse one.
- [**embedding**](#agrag-common-data_models-Community-embedding) (<code>list\[float\] | None</code>) – The community's dense vector, computed from title and
  summary. None before the report/embedding stage runs.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-Community-to_node_record) – Return this community as a GraphStore write record.

##### `agrag.common.data_models.Community.created_at` \{#agrag-common-data_models-Community-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

##### `agrag.common.data_models.Community.embedding` \{#agrag-common-data_models-Community-embedding}

```python
embedding: list[float] | None = None
```

##### `agrag.common.data_models.Community.embedding_text` \{#agrag-common-data_models-Community-embedding_text}

```python
embedding_text: str
```

Return the text this community's embedding is computed from.

##### `agrag.common.data_models.Community.findings` \{#agrag-common-data_models-Community-findings}

```python
findings: list[str] = Field(default_factory=list)
```

##### `agrag.common.data_models.Community.id` \{#agrag-common-data_models-Community-id}

```python
id: UUID
```

##### `agrag.common.data_models.Community.internal_weight` \{#agrag-common-data_models-Community-internal_weight}

```python
internal_weight: float = Field(default=0.0, ge=0.0)
```

##### `agrag.common.data_models.Community.member_ids` \{#agrag-common-data_models-Community-member_ids}

```python
member_ids: list[UUID] = Field(default_factory=list)
```

##### `agrag.common.data_models.Community.metadata` \{#agrag-common-data_models-Community-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Community.rating` \{#agrag-common-data_models-Community-rating}

```python
rating: float = Field(ge=0.0, le=10.0)
```

##### `agrag.common.data_models.Community.rating_explanation` \{#agrag-common-data_models-Community-rating_explanation}

```python
rating_explanation: str
```

##### `agrag.common.data_models.Community.summary` \{#agrag-common-data_models-Community-summary}

```python
summary: str
```

##### `agrag.common.data_models.Community.title` \{#agrag-common-data_models-Community-title}

```python
title: str
```

##### `agrag.common.data_models.Community.to_node_record` \{#agrag-common-data_models-Community-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this community as a GraphStore write record.

#### `agrag.common.data_models.Distance` \{#agrag-common-data_models-Distance}

Bases: <code>StrEnum</code>

A distance metric a vector index compares embeddings with.

**Attributes:**

- [**COSINE**](#agrag-common-data_models-Distance-COSINE) – Cosine similarity. The default for most embedding models.
- [**EUCLID**](#agrag-common-data_models-Distance-EUCLID) – Euclidean (L2) distance.
- [**DOT**](#agrag-common-data_models-Distance-DOT) – Dot product.

##### `agrag.common.data_models.Distance.COSINE` \{#agrag-common-data_models-Distance-COSINE}

```python
COSINE = 'Cosine'
```

##### `agrag.common.data_models.Distance.DOT` \{#agrag-common-data_models-Distance-DOT}

```python
DOT = 'Dot'
```

##### `agrag.common.data_models.Distance.EUCLID` \{#agrag-common-data_models-Distance-EUCLID}

```python
EUCLID = 'Euclid'
```

#### `agrag.common.data_models.Document` \{#agrag-common-data_models-Document}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

One unit of source text, before chunking.

A prose source, such as a Markdown file, makes one Document. A record source,
such as a CSV file, makes one Document per row.

The way the system computes `content_hash` depends on the loader. A text
loader hashes the decoded text. A docling loader hashes the raw source bytes
instead of the parsed output, because docling's parsed output can change
between docling versions and between runs on different hardware.

The system computes `id` from `content_hash` and `record_id` unless the caller
passes `id` directly. A record-family document without `record_id` also mixes
in `record_index` plus `source_hash`, or `uri` when `source_hash` is not
set. Pass `id` only when rebuilding a document from stored data.

**Attributes:**

- [**text**](#agrag-common-data_models-Document-text) (<code>str</code>) – The document text. For a docling source, this holds docling's Markdown
  export. The chunker never reads this field for a docling source; see the
  `Chunk` model for docling chunk content instead.
- [**title**](#agrag-common-data_models-Document-title) (<code>str</code>) – The document title.
- [**uri**](#agrag-common-data_models-Document-uri) (<code>str</code>) – The location of the source. This value is not part of the document id.
- [**source_format**](#agrag-common-data_models-Document-source_format) (<code>[SourceFormat](#agrag-common-data_models-document-SourceFormat)</code>) – The format the loader used to read this document.
- [**family**](#agrag-common-data_models-Document-family) (<code>[DocumentFamily](#agrag-common-data_models-document-DocumentFamily)</code>) – The shape of the source: one document per file, or one document per
  record.
- [**content_hash**](#agrag-common-data_models-Document-content_hash) (<code>str</code>) – The hash that forms the document id.
- [**loader_name**](#agrag-common-data_models-Document-loader_name) (<code>str</code>) – The name of the loader that produced this document, for example
  `"text"` or `"docling"`.
- [**loader_version**](#agrag-common-data_models-Document-loader_version) (<code>str | None</code>) – The version of the loader package. Does not affect the
  document id.
- [**encoding**](#agrag-common-data_models-Document-encoding) (<code>str | None</code>) – The text encoding. Text loaders set this field; other loaders
  leave it empty.
- [**source_hash**](#agrag-common-data_models-Document-source_hash) (<code>str | None</code>) – The hash of the whole source file. Record-family documents set
  this field.
- [**char_count**](#agrag-common-data_models-Document-char_count) (<code>int</code>) – The number of characters in `text`.
- [**line_count**](#agrag-common-data_models-Document-line_count) (<code>int | None</code>) – The number of lines in `text`. Some loaders do not set this field.
- [**record_index**](#agrag-common-data_models-Document-record_index) (<code>int | None</code>) – The 0-based row number in the source. Record-family documents
  set this field.
- [**record_id**](#agrag-common-data_models-Document-record_id) (<code>str | None</code>) – The value from the configured id column. Record-family documents
  set this field only when the caller configures an id column.
- [**raw_record**](#agrag-common-data_models-Document-raw_record) (<code>dict\[str, Any\] | None</code>) – The original record data. A loader sets this field only when the
  caller asks for it.
- [**heading_outline**](#agrag-common-data_models-Document-heading_outline) (<code>list\[[HeadingRef](#agrag-common-data_models-document-HeadingRef)\]</code>) – The headings in the document, with their offsets. A text
  loader sets this field for a prose document.
- [**document_key**](#agrag-common-data_models-Document-document_key) (<code>str | None</code>) – The stable identifier for this document's persisted graph node.
  Independent of `id`, which changes with every content edit. Defaults to
  `uri` when not supplied.
- [**turns**](#agrag-common-data_models-Document-turns) (<code>list\[[TurnRef](#agrag-common-data_models-document-TurnRef)\]</code>) – The speaker turns of a chat document, in order. A chat loader sets this
  field. Turn spans index `text` and do not overlap.
- [**normalization**](#agrag-common-data_models-Document-normalization) (<code>[Normalization](#agrag-common-data_models-normalization-Normalization) | None</code>) – How the loader normalized `text`. `None` for a document
  that no text loader made, such as a docling document or one built by hand.

**Functions:**

- [**id_for**](#agrag-common-data_models-Document-id_for) – Compute the document id.
- [**node_id_for**](#agrag-common-data_models-Document-node_id_for) – Compute the persisted Document graph node's id.
- [**to_node_record**](#agrag-common-data_models-Document-to_node_record) – Return this document as a GraphStore write record for its graph node.

##### `agrag.common.data_models.Document.char_count` \{#agrag-common-data_models-Document-char_count}

```python
char_count: int
```

##### `agrag.common.data_models.Document.content_hash` \{#agrag-common-data_models-Document-content_hash}

```python
content_hash: str
```

##### `agrag.common.data_models.Document.created_at` \{#agrag-common-data_models-Document-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

##### `agrag.common.data_models.Document.document_key` \{#agrag-common-data_models-Document-document_key}

```python
document_key: str | None = None
```

##### `agrag.common.data_models.Document.encoding` \{#agrag-common-data_models-Document-encoding}

```python
encoding: str | None = None
```

##### `agrag.common.data_models.Document.family` \{#agrag-common-data_models-Document-family}

```python
family: DocumentFamily
```

##### `agrag.common.data_models.Document.heading_outline` \{#agrag-common-data_models-Document-heading_outline}

```python
heading_outline: list[HeadingRef] = Field(default_factory=list)
```

##### `agrag.common.data_models.Document.id` \{#agrag-common-data_models-Document-id}

```python
id: UUID | None = None
```

##### `agrag.common.data_models.Document.id_for` \{#agrag-common-data_models-Document-id_for}

```python
id_for(*, content_hash:str, record_id:str | None = None, record_index:int | None = None, source_hash:str | None = None, uri:str | None = None) -> UUID
```

Compute the document id.

A record id, when given, wins over the content hash. Without a record id,
a record-family document (`record_index` is not `None`) mixes in its
source hash and row index, so two rows with identical text but no
configured id column still get distinct ids. When the source hash is not
available, this falls back to `uri` so that two different sources still
do not collide.

**Parameters:**

- **content_hash** (<code>str</code>) – The document's content hash.
- **record_id** (<code>str | None</code>) – The value from the configured id column, when the source has one.
- **record_index** (<code>int | None</code>) – The 0-based row number, for a record-family document.
- **source_hash** (<code>str | None</code>) – The hash of the whole source file, for a record-family
  document.
- **uri** (<code>str | None</code>) – The document's source location, used in place of `source_hash`
  when the caller does not supply one.

**Returns:**

- <code>UUID</code> – The document id.

##### `agrag.common.data_models.Document.line_count` \{#agrag-common-data_models-Document-line_count}

```python
line_count: int | None = None
```

##### `agrag.common.data_models.Document.loader_name` \{#agrag-common-data_models-Document-loader_name}

```python
loader_name: str
```

##### `agrag.common.data_models.Document.loader_version` \{#agrag-common-data_models-Document-loader_version}

```python
loader_version: str | None = None
```

##### `agrag.common.data_models.Document.metadata` \{#agrag-common-data_models-Document-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Document.node_id_for` \{#agrag-common-data_models-Document-node_id_for}

```python
node_id_for(*, document_key:str) -> UUID
```

Compute the persisted Document graph node's id.

Distinct from `id_for()`: this id is keyed on `document_key`, not the
content hash, so it stays the same across content changes to the same
logical document. Conflating the two ids would give every content version
of a document its own graph node instead of one node with a changing
content hash.

**Parameters:**

- **document_key** (<code>str</code>) – The document's stable key.

**Returns:**

- <code>UUID</code> – The Document graph node id.

##### `agrag.common.data_models.Document.normalization` \{#agrag-common-data_models-Document-normalization}

```python
normalization: Normalization | None = None
```

##### `agrag.common.data_models.Document.raw_record` \{#agrag-common-data_models-Document-raw_record}

```python
raw_record: dict[str, Any] | None = None
```

##### `agrag.common.data_models.Document.record_id` \{#agrag-common-data_models-Document-record_id}

```python
record_id: str | None = None
```

##### `agrag.common.data_models.Document.record_index` \{#agrag-common-data_models-Document-record_index}

```python
record_index: int | None = None
```

##### `agrag.common.data_models.Document.resolved_document_key` \{#agrag-common-data_models-Document-resolved_document_key}

```python
resolved_document_key: str
```

The document key, guaranteed non-`None` once construction succeeds.

`document_key` is typed as optional because callers may omit it and let
`_resolve_document_key` default it to `uri`, but every constructed
`Document` has a non-`None` document key by the time callers see it. Use
this property instead of `document_key` where a non-optional value is
required, such as computing the persisted Document node's id.

**Raises:**

- <code>RuntimeError</code> – `document_key` is still `None`, which means a validator
  was bypassed, for example via `model_construct`.

##### `agrag.common.data_models.Document.resolved_id` \{#agrag-common-data_models-Document-resolved_id}

```python
resolved_id: UUID
```

The document id, guaranteed non-`None` once construction succeeds.

`id` is typed as optional because callers may omit it and let
`_resolve_id` derive it, but every constructed `Document` has a
non-`None` id by the time callers see it. Use this property instead of
`id` where a non-optional value is required, such as building a `Chunk`.

**Raises:**

- <code>RuntimeError</code> – `id` is still `None`, which means a validator was
  bypassed, for example via `model_construct`.

##### `agrag.common.data_models.Document.source_format` \{#agrag-common-data_models-Document-source_format}

```python
source_format: SourceFormat
```

##### `agrag.common.data_models.Document.source_hash` \{#agrag-common-data_models-Document-source_hash}

```python
source_hash: str | None = None
```

##### `agrag.common.data_models.Document.text` \{#agrag-common-data_models-Document-text}

```python
text: str
```

##### `agrag.common.data_models.Document.title` \{#agrag-common-data_models-Document-title}

```python
title: str
```

##### `agrag.common.data_models.Document.to_node_record` \{#agrag-common-data_models-Document-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this document as a GraphStore write record for its graph node.

The record excludes `text`: the persisted node exists for traversal and
the update no-op check, not to duplicate the document body already held
per-chunk.

##### `agrag.common.data_models.Document.turns` \{#agrag-common-data_models-Document-turns}

```python
turns: list[TurnRef] = Field(default_factory=list)
```

##### `agrag.common.data_models.Document.uri` \{#agrag-common-data_models-Document-uri}

```python
uri: str
```

#### `agrag.common.data_models.DocumentFamily` \{#agrag-common-data_models-DocumentFamily}

Bases: <code>StrEnum</code>

The shape of a document's source.

**Attributes:**

- [**PROSE**](#agrag-common-data_models-DocumentFamily-PROSE) – One source file makes one document.
- [**RECORD**](#agrag-common-data_models-DocumentFamily-RECORD) – One source file makes many documents, one per record.

##### `agrag.common.data_models.DocumentFamily.PROSE` \{#agrag-common-data_models-DocumentFamily-PROSE}

```python
PROSE = 'prose'
```

##### `agrag.common.data_models.DocumentFamily.RECORD` \{#agrag-common-data_models-DocumentFamily-RECORD}

```python
RECORD = 'record'
```

#### `agrag.common.data_models.Entity` \{#agrag-common-data_models-Entity}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A permanent mention-level node, never destroyed once written.

Each Entity is one raw record: exact-match accumulation only folds a
new mention into the existing node for its normalized name. Fuzzy,
embedding, and LLM matches never absorb a node; they persist as
MATCHES edges with a derived ResolvedEntity instead, so both raw
records and their relationships survive resolution.

**Attributes:**

- [**label**](#agrag-common-data_models-Entity-label) (<code>str</code>) – The EntityType label this entity was resolved as.
- [**name**](#agrag-common-data_models-Entity-name) (<code>str</code>) – The canonical resolved surface form — field-resolved the same
  way any property is, but kept as its own field rather than
  inside properties, since every entity has one regardless of
  EntityType.properties' schema, and it is what gets embedded
  (embedding_text).
- [**properties**](#agrag-common-data_models-Entity-properties) (<code>dict\[str, object\]</code>) – Field-resolved property values, keyed by the schema's
  declared property names (e.g. "dosage", "description" — whatever
  EntityType.properties for this label declares). Never holds name.
- [**embedding**](#agrag-common-data_models-Entity-embedding) (<code>list\[float\] | None</code>) – The entity's dense vector, once populated by the storage
  stage. None before that point.
- [**merge_count**](#agrag-common-data_models-Entity-merge_count) (<code>int</code>) – The total number of source mentions this entity's data
  was assembled from. Starts at 1.
- [**source_chunk_ids**](#agrag-common-data_models-Entity-source_chunk_ids) (<code>list\[UUID\]</code>) – Ids of every Chunk a mention contributing to this
  entity's data came from. Each also backs one MENTIONED_IN edge
  from that Chunk to this Entity.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-Entity-to_node_record) – Return this entity as a GraphStore write record.

##### `agrag.common.data_models.Entity.created_at` \{#agrag-common-data_models-Entity-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

##### `agrag.common.data_models.Entity.embedding` \{#agrag-common-data_models-Entity-embedding}

```python
embedding: list[float] | None = None
```

##### `agrag.common.data_models.Entity.embedding_text` \{#agrag-common-data_models-Entity-embedding_text}

```python
embedding_text: str
```

Return the text this entity's embedding is computed from.

Name alone, or name plus a "description" property when the schema
declares one — decided once, here, so every embedding call site
(resolution's future embedding tier, storage-stage population,
Graph.consolidate()) embeds the same text for the same entity.

##### `agrag.common.data_models.Entity.id` \{#agrag-common-data_models-Entity-id}

```python
id: UUID
```

##### `agrag.common.data_models.Entity.label` \{#agrag-common-data_models-Entity-label}

```python
label: str
```

##### `agrag.common.data_models.Entity.merge_count` \{#agrag-common-data_models-Entity-merge_count}

```python
merge_count: int = 1
```

##### `agrag.common.data_models.Entity.merge_key` \{#agrag-common-data_models-Entity-merge_key}

```python
merge_key: str
```

Return this entity's global exact-match lookup key.

(label, normalized name) — the same identity ExactMatch already uses
in-batch, applied to a persisted store lookup. A derived value, not
stored redundantly anywhere else on this model; to_node_record()
computes it fresh from label/name every write, so it can never drift
from what the fields it's derived from actually say.

##### `agrag.common.data_models.Entity.metadata` \{#agrag-common-data_models-Entity-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Entity.name` \{#agrag-common-data_models-Entity-name}

```python
name: str
```

##### `agrag.common.data_models.Entity.properties` \{#agrag-common-data_models-Entity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Entity.source_chunk_ids` \{#agrag-common-data_models-Entity-source_chunk_ids}

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

##### `agrag.common.data_models.Entity.to_node_record` \{#agrag-common-data_models-Entity-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this entity as a GraphStore write record.

Name, merge_key, merge_count, and source_chunk_ids are
flattened into properties as plain JSON-safe values; GraphStore has
no reason to know these fields are special.

#### `agrag.common.data_models.EntityType` \{#agrag-common-data_models-EntityType}

Bases: <code>BaseModel</code>

One kind of entity a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-EntityType-label) (<code>str</code>) – The node label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-EntityType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**properties**](#agrag-common-data_models-EntityType-properties) (<code>dict\[str, str\]</code>) – Property names mapped to a type name, such as `"str"` or
  `"date"`. `label` and `text` are rejected, since both are
  vector payload keys retrieval filtering and keyword search use.
- [**subtypes**](#agrag-common-data_models-EntityType-subtypes) (<code>list\[str\]</code>) – Labels that narrow this type. Empty when this type has no subtypes.

##### `agrag.common.data_models.EntityType.description` \{#agrag-common-data_models-EntityType-description}

```python
description: str
```

##### `agrag.common.data_models.EntityType.label` \{#agrag-common-data_models-EntityType-label}

```python
label: str
```

##### `agrag.common.data_models.EntityType.properties` \{#agrag-common-data_models-EntityType-properties}

```python
properties: dict[str, str] = Field(default_factory=dict)
```

##### `agrag.common.data_models.EntityType.subtypes` \{#agrag-common-data_models-EntityType-subtypes}

```python
subtypes: list[str] = Field(default_factory=list)
```

#### `agrag.common.data_models.GENERIC` \{#agrag-common-data_models-GENERIC}

```python
GENERIC = GraphSchema(name='generic', version='1', entities=[EntityType(label='Person', description='A named individual.'), EntityType(label='Organization', description='A company or institution.'), EntityType(label='Location', description='A place or geographic area.'), EntityType(label='Event', description='A named occurrence at a time or place.'), EntityType(label='Product', description='A named product, service, or work.')], relations=[RelationType(label='RELATED_TO', description='A generic relationship between two entities.', patterns=[(src, tgt) for src in _GENERIC_LABELS for tgt in _GENERIC_LABELS])])
```

A ready-made schema for open-domain text.

It declares five entity types (`Person`, `Organization`, `Location`,
`Event`, and `Product`) and one relation, `RELATED_TO`, allowed between any
two of them. Use it to try agrag without writing a schema.

#### `agrag.common.data_models.GraphSchema` \{#agrag-common-data_models-GraphSchema}

Bases: <code>BaseModel</code>

A versioned contract of entity and relation types.

Every extraction call is validated against a GraphSchema; there is no schema-free
extraction path. Round-trip with `model_dump(mode="json")`/`model_validate()`.
A schema declaring an entity property name the vector payload reserves fails that
validation, so a payload written before the check existed must be migrated before
it loads again. See `EntityType.properties`.

**Attributes:**

- [**name**](#agrag-common-data_models-GraphSchema-name) (<code>str</code>) – A short, unique name for this schema.
- [**version**](#agrag-common-data_models-GraphSchema-version) (<code>str</code>) – The schema version. Bump when types or patterns change.
- [**entities**](#agrag-common-data_models-GraphSchema-entities) (<code>list\[[EntityType](#agrag-common-data_models-graph_schema-EntityType)\]</code>) – The entity types this schema recognizes.
- [**relations**](#agrag-common-data_models-GraphSchema-relations) (<code>list\[[RelationType](#agrag-common-data_models-graph_schema-RelationType)\]</code>) – The relation types this schema recognizes.

**Functions:**

- [**to_compact_summary**](#agrag-common-data_models-GraphSchema-to_compact_summary) – Serialize only entity labels and relation patterns for a prompt.
- [**to_prompt_description**](#agrag-common-data_models-GraphSchema-to_prompt_description) – Serialize this schema in full for an LLM prompt.

##### `agrag.common.data_models.GraphSchema.entities` \{#agrag-common-data_models-GraphSchema-entities}

```python
entities: list[EntityType]
```

##### `agrag.common.data_models.GraphSchema.name` \{#agrag-common-data_models-GraphSchema-name}

```python
name: str
```

##### `agrag.common.data_models.GraphSchema.relations` \{#agrag-common-data_models-GraphSchema-relations}

```python
relations: list[RelationType]
```

##### `agrag.common.data_models.GraphSchema.to_compact_summary` \{#agrag-common-data_models-GraphSchema-to_compact_summary}

```python
to_compact_summary() -> str
```

Serialize only entity labels and relation patterns for a prompt.

Descriptions, properties, and subtypes are omitted, so this is the
shape to inject where prompt space is tight.
:meth:`to_prompt_description` carries the same labels with their
full detail.

**Returns:**

- <code>str</code> – A plain-text summary of entity labels and valid relation
- <code>str</code> – patterns.

##### `agrag.common.data_models.GraphSchema.to_prompt_description` \{#agrag-common-data_models-GraphSchema-to_prompt_description}

```python
to_prompt_description() -> str
```

Serialize this schema in full for an LLM prompt.

Every entity type's label, description, declared properties, and
subtypes are listed, followed by every relation type's label,
description, and valid (source, target) patterns. Use
:meth:`to_compact_summary` instead when prompt space is tight.

**Returns:**

- <code>str</code> – A plain-text schema description, one fact per line.

##### `agrag.common.data_models.GraphSchema.version` \{#agrag-common-data_models-GraphSchema-version}

```python
version: str
```

#### `agrag.common.data_models.NodeRecord` \{#agrag-common-data_models-NodeRecord}

Bases: <code>BaseModel</code>

One graph node, ready to write.

**Attributes:**

- [**id**](#agrag-common-data_models-NodeRecord-id) (<code>UUID</code>) – The node id.
- [**labels**](#agrag-common-data_models-NodeRecord-labels) (<code>list\[str\]</code>) – The node's labels. A node carries every label listed here;
  `GraphStore.upsert_nodes` groups records by their full label set
  within a batch, since Cypher requires labels to be literal in the
  query rather than a runtime parameter.
- [**properties**](#agrag-common-data_models-NodeRecord-properties) (<code>dict\[str, Any\]</code>) – The node's properties, including an embedding vector under
  whatever key `GraphStore.ensure_vector_index` was configured
  with, if native vector search is in use.

**Functions:**

- [**reject_pending_tag**](#agrag-common-data_models-NodeRecord-reject_pending_tag) – Reject the job-owned tag in external graph records.

##### `agrag.common.data_models.NodeRecord.id` \{#agrag-common-data_models-NodeRecord-id}

```python
id: UUID
```

##### `agrag.common.data_models.NodeRecord.labels` \{#agrag-common-data_models-NodeRecord-labels}

```python
labels: list[str] = Field(min_length=1)
```

##### `agrag.common.data_models.NodeRecord.properties` \{#agrag-common-data_models-NodeRecord-properties}

```python
properties: dict[str, Any]
```

##### `agrag.common.data_models.NodeRecord.reject_pending_tag` \{#agrag-common-data_models-NodeRecord-reject_pending_tag}

```python
reject_pending_tag(properties:dict[str, Any]) -> dict[str, Any]
```

Reject the job-owned tag in external graph records.

#### `agrag.common.data_models.Normalization` \{#agrag-common-data_models-Normalization}

Bases: <code>BaseModel</code>

How a loader turned source bytes into `Document.text`.

Provenance offsets index the normalized text. A caller who needs offsets into
the raw source chooses `Normalization(bom="keep", newline="keep", unicode_form="none")`.

**Attributes:**

- [**bom**](#agrag-common-data_models-Normalization-bom) (<code>Literal['strip', 'keep']</code>) – `"strip"` removes a leading byte-order mark. `"keep"` leaves it.
- [**newline**](#agrag-common-data_models-Normalization-newline) (<code>Literal['lf', 'keep']</code>) – `"lf"` turns CRLF and CR into LF. `"keep"` leaves them.
- [**unicode_form**](#agrag-common-data_models-Normalization-unicode_form) (<code>Literal['NFKC', 'NFC', 'NFD', 'NFKD', 'none']</code>) – The Unicode normalization form to apply, or `"none"`.

##### `agrag.common.data_models.Normalization.bom` \{#agrag-common-data_models-Normalization-bom}

```python
bom: Literal['strip', 'keep'] = 'strip'
```

##### `agrag.common.data_models.Normalization.model_config` \{#agrag-common-data_models-Normalization-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

##### `agrag.common.data_models.Normalization.newline` \{#agrag-common-data_models-Normalization-newline}

```python
newline: Literal['lf', 'keep'] = 'lf'
```

##### `agrag.common.data_models.Normalization.unicode_form` \{#agrag-common-data_models-Normalization-unicode_form}

```python
unicode_form: Literal['NFKC', 'NFC', 'NFD', 'NFKD', 'none'] = 'NFKC'
```

#### `agrag.common.data_models.PageProvenance` \{#agrag-common-data_models-PageProvenance}

Bases: <code>BaseModel</code>

The location of a chunk across one or more pages.

A chunk can start on one page and end on the next page. Each entry in `page_spans`
covers one page.

**Attributes:**

- [**kind**](#agrag-common-data_models-PageProvenance-kind) (<code>Literal['page']</code>) – The literal tag `"page"`. Marks this as page provenance.
- [**page_spans**](#agrag-common-data_models-PageProvenance-page_spans) (<code>list\[[PageSpan](#agrag-common-data_models-provenance-PageSpan)\]</code>) – The page spans for this chunk. Has more than one entry when
  the chunk crosses a page boundary.

##### `agrag.common.data_models.PageProvenance.kind` \{#agrag-common-data_models-PageProvenance-kind}

```python
kind: Literal['page'] = 'page'
```

##### `agrag.common.data_models.PageProvenance.page_spans` \{#agrag-common-data_models-PageProvenance-page_spans}

```python
page_spans: list[PageSpan]
```

#### `agrag.common.data_models.Relation` \{#agrag-common-data_models-Relation}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A resolved relationship between two Entity nodes.

**Attributes:**

- [**type**](#agrag-common-data_models-Relation-type) (<code>str</code>) – The RelationType label this relationship was resolved as.
- [**source_id**](#agrag-common-data_models-Relation-source_id) (<code>UUID</code>) – The id of the source Entity.
- [**target_id**](#agrag-common-data_models-Relation-target_id) (<code>UUID</code>) – The id of the target Entity.
- [**properties**](#agrag-common-data_models-Relation-properties) (<code>dict\[str, object\]</code>) – Field-resolved property values.
- [**source_chunk_ids**](#agrag-common-data_models-Relation-source_chunk_ids) (<code>list\[UUID\]</code>) – Ids of every Chunk a mention contributing to this
  relationship came from. A relationship attested by more than one
  source has more than one id here, rather than existing as
  parallel edges.

**Functions:**

- [**to_relation_record**](#agrag-common-data_models-Relation-to_relation_record) – Return this relationship as a GraphStore write record.

##### `agrag.common.data_models.Relation.created_at` \{#agrag-common-data_models-Relation-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

##### `agrag.common.data_models.Relation.id` \{#agrag-common-data_models-Relation-id}

```python
id: UUID
```

##### `agrag.common.data_models.Relation.metadata` \{#agrag-common-data_models-Relation-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Relation.properties` \{#agrag-common-data_models-Relation-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

##### `agrag.common.data_models.Relation.source_chunk_ids` \{#agrag-common-data_models-Relation-source_chunk_ids}

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

##### `agrag.common.data_models.Relation.source_id` \{#agrag-common-data_models-Relation-source_id}

```python
source_id: UUID
```

##### `agrag.common.data_models.Relation.target_id` \{#agrag-common-data_models-Relation-target_id}

```python
target_id: UUID
```

##### `agrag.common.data_models.Relation.to_relation_record` \{#agrag-common-data_models-Relation-to_relation_record}

```python
to_relation_record() -> RelationRecord
```

Return this relationship as a GraphStore write record.

##### `agrag.common.data_models.Relation.type` \{#agrag-common-data_models-Relation-type}

```python
type: str
```

#### `agrag.common.data_models.RelationRecord` \{#agrag-common-data_models-RelationRecord}

Bases: <code>BaseModel</code>

One graph relationship, ready to write.

**Attributes:**

- [**id**](#agrag-common-data_models-RelationRecord-id) (<code>UUID</code>) – The relationship id.
- [**type**](#agrag-common-data_models-RelationRecord-type) (<code>str</code>) – The relationship type.
- [**start_id**](#agrag-common-data_models-RelationRecord-start_id) (<code>UUID</code>) – The id of the start node.
- [**end_id**](#agrag-common-data_models-RelationRecord-end_id) (<code>UUID</code>) – The id of the end node.
- [**properties**](#agrag-common-data_models-RelationRecord-properties) (<code>dict\[str, Any\]</code>) – The relationship's properties.

**Functions:**

- [**reject_pending_tag**](#agrag-common-data_models-RelationRecord-reject_pending_tag) – Reject the job-owned tag in external graph records.

##### `agrag.common.data_models.RelationRecord.end_id` \{#agrag-common-data_models-RelationRecord-end_id}

```python
end_id: UUID
```

##### `agrag.common.data_models.RelationRecord.id` \{#agrag-common-data_models-RelationRecord-id}

```python
id: UUID
```

##### `agrag.common.data_models.RelationRecord.properties` \{#agrag-common-data_models-RelationRecord-properties}

```python
properties: dict[str, Any]
```

##### `agrag.common.data_models.RelationRecord.reject_pending_tag` \{#agrag-common-data_models-RelationRecord-reject_pending_tag}

```python
reject_pending_tag(properties:dict[str, Any]) -> dict[str, Any]
```

Reject the job-owned tag in external graph records.

##### `agrag.common.data_models.RelationRecord.start_id` \{#agrag-common-data_models-RelationRecord-start_id}

```python
start_id: UUID
```

##### `agrag.common.data_models.RelationRecord.type` \{#agrag-common-data_models-RelationRecord-type}

```python
type: str
```

#### `agrag.common.data_models.RelationType` \{#agrag-common-data_models-RelationType}

Bases: <code>BaseModel</code>

One kind of relation a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-RelationType-label) (<code>str</code>) – The relation label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-RelationType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**patterns**](#agrag-common-data_models-RelationType-patterns) (<code>list\[tuple\[str, str\]\]</code>) – Valid (source_label, target_label) pairs for this relation. An
  extraction whose triple is not in this list is dropped at normalize time.

##### `agrag.common.data_models.RelationType.description` \{#agrag-common-data_models-RelationType-description}

```python
description: str
```

##### `agrag.common.data_models.RelationType.label` \{#agrag-common-data_models-RelationType-label}

```python
label: str
```

##### `agrag.common.data_models.RelationType.patterns` \{#agrag-common-data_models-RelationType-patterns}

```python
patterns: list[tuple[str, str]]
```

#### `agrag.common.data_models.ResolvedEntity` \{#agrag-common-data_models-ResolvedEntity}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A materialized cluster of entities that refer to the same thing.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-ResolvedEntity-to_node_record) – Return this resolved entity as a graph write record.

**Attributes:**

- [**created_at**](#agrag-common-data_models-ResolvedEntity-created_at) (<code>datetime</code>) –
- [**embedding**](#agrag-common-data_models-ResolvedEntity-embedding) (<code>list\[float\] | None</code>) –
- [**embedding_text**](#agrag-common-data_models-ResolvedEntity-embedding_text) (<code>str</code>) – Return the text used to embed this resolved entity.
- [**id**](#agrag-common-data_models-ResolvedEntity-id) (<code>UUID</code>) –
- [**label**](#agrag-common-data_models-ResolvedEntity-label) (<code>str</code>) –
- [**member_ids**](#agrag-common-data_models-ResolvedEntity-member_ids) (<code>list\[UUID\]</code>) –
- [**metadata**](#agrag-common-data_models-ResolvedEntity-metadata) (<code>dict\[str, Any\]</code>) –
- [**name**](#agrag-common-data_models-ResolvedEntity-name) (<code>str</code>) –
- [**properties**](#agrag-common-data_models-ResolvedEntity-properties) (<code>dict\[str, object\]</code>) –
- [**vector_sync_error**](#agrag-common-data_models-ResolvedEntity-vector_sync_error) (<code>str | None</code>) –
- [**vector_sync_status**](#agrag-common-data_models-ResolvedEntity-vector_sync_status) (<code>Literal['pending', 'synced', 'failed']</code>) –

##### `agrag.common.data_models.ResolvedEntity.created_at` \{#agrag-common-data_models-ResolvedEntity-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

##### `agrag.common.data_models.ResolvedEntity.embedding` \{#agrag-common-data_models-ResolvedEntity-embedding}

```python
embedding: list[float] | None = None
```

##### `agrag.common.data_models.ResolvedEntity.embedding_text` \{#agrag-common-data_models-ResolvedEntity-embedding_text}

```python
embedding_text: str
```

Return the text used to embed this resolved entity.

##### `agrag.common.data_models.ResolvedEntity.id` \{#agrag-common-data_models-ResolvedEntity-id}

```python
id: UUID
```

##### `agrag.common.data_models.ResolvedEntity.label` \{#agrag-common-data_models-ResolvedEntity-label}

```python
label: str
```

##### `agrag.common.data_models.ResolvedEntity.member_ids` \{#agrag-common-data_models-ResolvedEntity-member_ids}

```python
member_ids: list[UUID] = Field(default_factory=list)
```

##### `agrag.common.data_models.ResolvedEntity.metadata` \{#agrag-common-data_models-ResolvedEntity-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.ResolvedEntity.name` \{#agrag-common-data_models-ResolvedEntity-name}

```python
name: str
```

##### `agrag.common.data_models.ResolvedEntity.properties` \{#agrag-common-data_models-ResolvedEntity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

##### `agrag.common.data_models.ResolvedEntity.to_node_record` \{#agrag-common-data_models-ResolvedEntity-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this resolved entity as a graph write record.

##### `agrag.common.data_models.ResolvedEntity.vector_sync_error` \{#agrag-common-data_models-ResolvedEntity-vector_sync_error}

```python
vector_sync_error: str | None = None
```

##### `agrag.common.data_models.ResolvedEntity.vector_sync_status` \{#agrag-common-data_models-ResolvedEntity-vector_sync_status}

```python
vector_sync_status: Literal['pending', 'synced', 'failed'] = 'pending'
```

#### `agrag.common.data_models.SearchResult` \{#agrag-common-data_models-SearchResult}

Bases: <code>BaseModel</code>

One retrieved item, tagged with where it came from.

**Attributes:**

- [**item**](#agrag-common-data_models-SearchResult-item) (<code>Union\[[Entity](#agrag-common-data_models-entity-Entity), [ResolvedEntity](#agrag-common-data_models-resolved_entity-ResolvedEntity), [Relation](#agrag-common-data_models-relation-Relation), [Chunk](#agrag-common-data_models-chunk-Chunk), [Community](#agrag-common-data_models-community-Community), [QueryValue](#agrag-common-data_models-query_value-QueryValue)\]</code>) – The retrieved Entity, ResolvedEntity, Relation, Chunk, or
  Community, or scalar query value.
- [**score**](#agrag-common-data_models-SearchResult-score) (<code>float</code>) – The method's own relevance score. Not comparable
  across methods until Fusion normalizes it.
- [**method**](#agrag-common-data_models-SearchResult-method) (<code>str</code>) – The name of the retrieval method that produced
  this result.
- [**parent**](#agrag-common-data_models-SearchResult-parent) (<code>[Chunk](#agrag-common-data_models-chunk-Chunk) | None</code>) – The parent chunk of a child chunk result, so a caller can show the
  larger passage. `None` for every other result.

##### `agrag.common.data_models.SearchResult.identity_key` \{#agrag-common-data_models-SearchResult-identity_key}

```python
identity_key: tuple[str, UUID]
```

Return the (type, id) key Fusion deduplicates on.

**Raises:**

- <code>ValueError</code> – The item has no id, so it cannot be
  deduplicated.

##### `agrag.common.data_models.SearchResult.item` \{#agrag-common-data_models-SearchResult-item}

```python
item: Union[Entity, ResolvedEntity, Relation, Chunk, Community, QueryValue]
```

##### `agrag.common.data_models.SearchResult.method` \{#agrag-common-data_models-SearchResult-method}

```python
method: str
```

##### `agrag.common.data_models.SearchResult.parent` \{#agrag-common-data_models-SearchResult-parent}

```python
parent: Chunk | None = None
```

##### `agrag.common.data_models.SearchResult.score` \{#agrag-common-data_models-SearchResult-score}

```python
score: float
```

#### `agrag.common.data_models.SourceFormat` \{#agrag-common-data_models-SourceFormat}

Bases: <code>StrEnum</code>

A source format that a loader can read.

The field that holds this value is named `source_format`, not `format`.
`format`
is a Python builtin, and this project's lint rules reject builtin names for fields.

**Attributes:**

- [**ASCIIDOC**](#agrag-common-data_models-SourceFormat-ASCIIDOC) –
- [**CSV**](#agrag-common-data_models-SourceFormat-CSV) –
- [**DOCX**](#agrag-common-data_models-SourceFormat-DOCX) –
- [**HTML**](#agrag-common-data_models-SourceFormat-HTML) –
- [**IMAGE**](#agrag-common-data_models-SourceFormat-IMAGE) –
- [**JSON**](#agrag-common-data_models-SourceFormat-JSON) –
- [**JSONL**](#agrag-common-data_models-SourceFormat-JSONL) –
- [**LOG**](#agrag-common-data_models-SourceFormat-LOG) –
- [**MARKDOWN**](#agrag-common-data_models-SourceFormat-MARKDOWN) –
- [**PDF**](#agrag-common-data_models-SourceFormat-PDF) –
- [**PPTX**](#agrag-common-data_models-SourceFormat-PPTX) –
- [**TSV**](#agrag-common-data_models-SourceFormat-TSV) –
- [**TXT**](#agrag-common-data_models-SourceFormat-TXT) –
- [**XML**](#agrag-common-data_models-SourceFormat-XML) –

##### `agrag.common.data_models.SourceFormat.ASCIIDOC` \{#agrag-common-data_models-SourceFormat-ASCIIDOC}

```python
ASCIIDOC = 'asciidoc'
```

##### `agrag.common.data_models.SourceFormat.CSV` \{#agrag-common-data_models-SourceFormat-CSV}

```python
CSV = 'csv'
```

##### `agrag.common.data_models.SourceFormat.DOCX` \{#agrag-common-data_models-SourceFormat-DOCX}

```python
DOCX = 'docx'
```

##### `agrag.common.data_models.SourceFormat.HTML` \{#agrag-common-data_models-SourceFormat-HTML}

```python
HTML = 'html'
```

##### `agrag.common.data_models.SourceFormat.IMAGE` \{#agrag-common-data_models-SourceFormat-IMAGE}

```python
IMAGE = 'image'
```

##### `agrag.common.data_models.SourceFormat.JSON` \{#agrag-common-data_models-SourceFormat-JSON}

```python
JSON = 'json'
```

##### `agrag.common.data_models.SourceFormat.JSONL` \{#agrag-common-data_models-SourceFormat-JSONL}

```python
JSONL = 'jsonl'
```

##### `agrag.common.data_models.SourceFormat.LOG` \{#agrag-common-data_models-SourceFormat-LOG}

```python
LOG = 'log'
```

##### `agrag.common.data_models.SourceFormat.MARKDOWN` \{#agrag-common-data_models-SourceFormat-MARKDOWN}

```python
MARKDOWN = 'markdown'
```

##### `agrag.common.data_models.SourceFormat.PDF` \{#agrag-common-data_models-SourceFormat-PDF}

```python
PDF = 'pdf'
```

##### `agrag.common.data_models.SourceFormat.PPTX` \{#agrag-common-data_models-SourceFormat-PPTX}

```python
PPTX = 'pptx'
```

##### `agrag.common.data_models.SourceFormat.TSV` \{#agrag-common-data_models-SourceFormat-TSV}

```python
TSV = 'tsv'
```

##### `agrag.common.data_models.SourceFormat.TXT` \{#agrag-common-data_models-SourceFormat-TXT}

```python
TXT = 'txt'
```

##### `agrag.common.data_models.SourceFormat.XML` \{#agrag-common-data_models-SourceFormat-XML}

```python
XML = 'xml'
```

#### `agrag.common.data_models.TextProvenance` \{#agrag-common-data_models-TextProvenance}

Bases: <code>BaseModel</code>

The location of a chunk inside flattened document text.

The offsets index the normalized text in `Document.text`, not the raw source.
See `Normalization`.

**Attributes:**

- [**kind**](#agrag-common-data_models-TextProvenance-kind) (<code>Literal['text']</code>) – The literal tag `"text"`. Marks this as text provenance.
- [**char_start**](#agrag-common-data_models-TextProvenance-char_start) (<code>int</code>) – The start character offset in the document text.
- [**char_end**](#agrag-common-data_models-TextProvenance-char_end) (<code>int</code>) – The end character offset in the document text.
- [**line_start**](#agrag-common-data_models-TextProvenance-line_start) (<code>int | None</code>) – The start line number. Empty when the loader does not track lines.
- [**line_end**](#agrag-common-data_models-TextProvenance-line_end) (<code>int | None</code>) – The end line number. Empty when the loader does not track lines.

##### `agrag.common.data_models.TextProvenance.char_end` \{#agrag-common-data_models-TextProvenance-char_end}

```python
char_end: int
```

##### `agrag.common.data_models.TextProvenance.char_start` \{#agrag-common-data_models-TextProvenance-char_start}

```python
char_start: int
```

##### `agrag.common.data_models.TextProvenance.kind` \{#agrag-common-data_models-TextProvenance-kind}

```python
kind: Literal['text'] = 'text'
```

##### `agrag.common.data_models.TextProvenance.line_end` \{#agrag-common-data_models-TextProvenance-line_end}

```python
line_end: int | None = None
```

##### `agrag.common.data_models.TextProvenance.line_start` \{#agrag-common-data_models-TextProvenance-line_start}

```python
line_start: int | None = None
```

#### `agrag.common.data_models.VectorRecord` \{#agrag-common-data_models-VectorRecord}

Bases: <code>BaseModel</code>

One vector and its payload, ready to write to a collection or index.

The collection or index name is a call argument on the store, not a field
here, so one record type can target any collection.

**Attributes:**

- [**id**](#agrag-common-data_models-VectorRecord-id) (<code>UUID</code>) – The record id. Callers set this to the id of the domain object the
  vector represents.
- [**vector**](#agrag-common-data_models-VectorRecord-vector) (<code>list\[float\]</code>) – The dense embedding.
- [**payload**](#agrag-common-data_models-VectorRecord-payload) (<code>dict\[str, Any\]</code>) – Fields stored alongside the vector, such as the source text or
  a chunk id. Read back unchanged by `search`/`hybrid_search`.

##### `agrag.common.data_models.VectorRecord.id` \{#agrag-common-data_models-VectorRecord-id}

```python
id: UUID
```

##### `agrag.common.data_models.VectorRecord.payload` \{#agrag-common-data_models-VectorRecord-payload}

```python
payload: dict[str, Any]
```

##### `agrag.common.data_models.VectorRecord.vector` \{#agrag-common-data_models-VectorRecord-vector}

```python
vector: list[float]
```

#### `agrag.common.data_models.chunk` \{#agrag-common-data_models-chunk}

The Chunk model: one retrieval-sized piece of a Document.

**Classes:**

- [**Chunk**](#agrag-common-data_models-chunk-Chunk) – One retrieval-sized piece of a Document.

**Attributes:**

- [**CHUNK_LABEL**](#agrag-common-data_models-chunk-CHUNK_LABEL) –

##### `agrag.common.data_models.chunk.CHUNK_LABEL` \{#agrag-common-data_models-chunk-CHUNK_LABEL}

```python
CHUNK_LABEL = 'Chunk'
```

##### `agrag.common.data_models.chunk.Chunk` \{#agrag-common-data_models-chunk-Chunk}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

One retrieval-sized piece of a Document.

**Attributes:**

- [**document_id**](#agrag-common-data_models-chunk-Chunk-document_id) (<code>UUID</code>) – The id of the persisted Document graph node this chunk
  belongs to (see `Document.node_id_for`). Stable across content
  versions of the same logical document; per-version identity lives
  in `Chunk.id` instead.
- [**index**](#agrag-common-data_models-chunk-Chunk-index) (<code>int</code>) – The position of the chunk within its document, from 0.
- [**text**](#agrag-common-data_models-chunk-Chunk-text) (<code>str</code>) – The chunk text.
- [**provenance**](#agrag-common-data_models-chunk-Chunk-provenance) (<code>[TextProvenance](#agrag-common-data_models-provenance-TextProvenance) | [PageProvenance](#agrag-common-data_models-provenance-PageProvenance)</code>) – The location of this chunk in its source. The shape of this
  value depends on which chunker made the chunk.
- [**heading_path**](#agrag-common-data_models-chunk-Chunk-heading_path) (<code>list\[str\]</code>) – The headings that contain this chunk, from outermost to innermost.
  Empty for a docling chunk and for a chunk with no heading above it.
- [**content_kind**](#agrag-common-data_models-chunk-Chunk-content_kind) (<code>Literal['text', 'table_row', 'code', 'heading']</code>) – The kind of content in this chunk. A text chunker always sets
  `"text"`. A docling chunk can also be `"table_row"`.
- [**chunker**](#agrag-common-data_models-chunk-Chunk-chunker) (<code>str | None</code>) – The strategy name of the chunker that made this chunk. `None` for a
  chunk written before chunkers were recorded.
- [**chunker_hash**](#agrag-common-data_models-chunk-Chunk-chunker_hash) (<code>str | None</code>) – The fingerprint of the settings of the chunker that made this
  chunk. `None` for a chunk written before chunkers were recorded.
- [**level**](#agrag-common-data_models-chunk-Chunk-level) (<code>int</code>) – `1` for a parent chunk, `0` for every other chunk. A parent
  chunk is the unit of extraction. A child chunk is the unit of search.
- [**parent_id**](#agrag-common-data_models-chunk-Chunk-parent_id) (<code>UUID | None</code>) – The id of the parent chunk of a child chunk. `None` for a
  parent and for a chunk that has no parent.

**Functions:**

- [**id_for**](#agrag-common-data_models-chunk-Chunk-id_for) – Compute the chunk id.
- [**section_label**](#agrag-common-data_models-chunk-Chunk-section_label) – Return the heading path as one line, or `None` when the path is empty.
- [**to_node_record**](#agrag-common-data_models-chunk-Chunk-to_node_record) – Return this chunk as a GraphStore write record.

###### `agrag.common.data_models.chunk.Chunk.chunker` \{#agrag-common-data_models-chunk-Chunk-chunker}

```python
chunker: str | None = None
```

###### `agrag.common.data_models.chunk.Chunk.chunker_hash` \{#agrag-common-data_models-chunk-Chunk-chunker_hash}

```python
chunker_hash: str | None = None
```

###### `agrag.common.data_models.chunk.Chunk.content_kind` \{#agrag-common-data_models-chunk-Chunk-content_kind}

```python
content_kind: Literal['text', 'table_row', 'code', 'heading'] = 'text'
```

###### `agrag.common.data_models.chunk.Chunk.contextual_text` \{#agrag-common-data_models-chunk-Chunk-contextual_text}

```python
contextual_text: str
```

The text with its heading path above it, for embedding.

The stored text and its offsets do not change. A chunk with no heading path
returns its text.

###### `agrag.common.data_models.chunk.Chunk.created_at` \{#agrag-common-data_models-chunk-Chunk-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.chunk.Chunk.document_id` \{#agrag-common-data_models-chunk-Chunk-document_id}

```python
document_id: UUID
```

###### `agrag.common.data_models.chunk.Chunk.embedding` \{#agrag-common-data_models-chunk-Chunk-embedding}

```python
embedding: list[float] | None = None
```

###### `agrag.common.data_models.chunk.Chunk.heading_path` \{#agrag-common-data_models-chunk-Chunk-heading_path}

```python
heading_path: list[str] = Field(default_factory=list)
```

###### `agrag.common.data_models.chunk.Chunk.id` \{#agrag-common-data_models-chunk-Chunk-id}

```python
id: UUID | None = None
```

###### `agrag.common.data_models.chunk.Chunk.id_for` \{#agrag-common-data_models-chunk-Chunk-id_for}

```python
id_for(*, document_id:UUID, version_id:UUID | None = None, provenance:TextProvenance | PageProvenance, index:int, chunker_hash:str | None = None, level:int = 0) -> UUID
```

Compute the chunk id.

For a text chunk, the id comes from the document id and the character span. A
change in chunk size shifts the span, so it also changes the id. When supplied,
`version_id` makes the id distinct for each version of a document.

For a docling chunk, the id comes from the document id, the chunker hash and
the chunk index instead. The hash keeps a re-chunk with new settings from
overwriting chunk N of the earlier settings. Docling parsing is not always the
same between runs, so this id is not stable across a re-parse of the same
source.

**Parameters:**

- **document_id** (<code>UUID</code>) – The id of the parent Document.
- **version_id** (<code>UUID | None</code>) – Optional id for the parent document version.
- **provenance** (<code>[TextProvenance](#agrag-common-data_models-provenance-TextProvenance) | [PageProvenance](#agrag-common-data_models-provenance-PageProvenance)</code>) – The provenance of the chunk. Its type picks which id rule
  applies.
- **index** (<code>int</code>) – The position of the chunk within its document.
- **chunker_hash** (<code>str | None</code>) – The fingerprint of the chunker. Only a docling chunk uses
  it; a text chunk id ignores it.
- **level** (<code>int</code>) – The chunk level. A parent chunk (level 1) adds a level part, so a
  parent and a child with the same span get different ids. The id of a
  level 0 chunk does not change.

**Returns:**

- <code>UUID</code> – The chunk id.

###### `agrag.common.data_models.chunk.Chunk.index` \{#agrag-common-data_models-chunk-Chunk-index}

```python
index: int = 0
```

###### `agrag.common.data_models.chunk.Chunk.level` \{#agrag-common-data_models-chunk-Chunk-level}

```python
level: int = 0
```

###### `agrag.common.data_models.chunk.Chunk.metadata` \{#agrag-common-data_models-chunk-Chunk-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.chunk.Chunk.parent_id` \{#agrag-common-data_models-chunk-Chunk-parent_id}

```python
parent_id: UUID | None = None
```

###### `agrag.common.data_models.chunk.Chunk.provenance` \{#agrag-common-data_models-chunk-Chunk-provenance}

```python
provenance: TextProvenance | PageProvenance = Field(discriminator='kind')
```

###### `agrag.common.data_models.chunk.Chunk.section_label` \{#agrag-common-data_models-chunk-Chunk-section_label}

```python
section_label() -> str | None
```

Return the heading path as one line, or `None` when the path is empty.

Whitespace runs in a heading become one space, and runs of three or more
dashes become one dash, so a heading cannot end the text block of the
extraction prompt.

###### `agrag.common.data_models.chunk.Chunk.text` \{#agrag-common-data_models-chunk-Chunk-text}

```python
text: str
```

###### `agrag.common.data_models.chunk.Chunk.to_node_record` \{#agrag-common-data_models-chunk-Chunk-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this chunk as a GraphStore write record.

Provenance is flattened to a plain JSON-safe dict via model_dump —
GraphStore's own serialize.node_params only converts UUIDs and walks
containers.

**Raises:**

- <code>ValueError</code> – id is None.

#### `agrag.common.data_models.community` \{#agrag-common-data_models-community}

The Community model: a Leiden-detected entity cluster with an LLM report.

**Classes:**

- [**Community**](#agrag-common-data_models-community-Community) – A cluster of entities detected by hierarchical Leiden, with an LLM report.

**Attributes:**

- [**COMMUNITY_LABEL**](#agrag-common-data_models-community-COMMUNITY_LABEL) –
- [**MEMBER_OF_RELATION**](#agrag-common-data_models-community-MEMBER_OF_RELATION) –

##### `agrag.common.data_models.community.COMMUNITY_LABEL` \{#agrag-common-data_models-community-COMMUNITY_LABEL}

```python
COMMUNITY_LABEL = 'Community'
```

##### `agrag.common.data_models.community.Community` \{#agrag-common-data_models-community-Community}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A cluster of entities detected by hierarchical Leiden, with an LLM report.

**Attributes:**

- [**title**](#agrag-common-data_models-community-Community-title) (<code>str</code>) – A short, human-readable name for the community.
- [**summary**](#agrag-common-data_models-community-Community-summary) (<code>str</code>) – A prose summary of what the community is about.
- [**rating**](#agrag-common-data_models-community-Community-rating) (<code>float</code>) – An importance rating for this community, 0-10.
- [**rating_explanation**](#agrag-common-data_models-community-Community-rating_explanation) (<code>str</code>) – One sentence explaining the rating.
- [**findings**](#agrag-common-data_models-community-Community-findings) (<code>list\[str\]</code>) – Distinct factual claims the report supports.
- [**member_ids**](#agrag-common-data_models-community-Community-member_ids) (<code>list\[UUID\]</code>) – Ids of every Entity in this community, ordered by
  internal weighted degree descending (see compute_communities) --
  the highest-centrality, most representative members first.
- [**internal_weight**](#agrag-common-data_models-community-Community-internal_weight) (<code>float</code>) – Total weight of edges where both endpoints are
  members of this community. A free-to-compute (no extra query,
  no new dependency) importance signal, used in place of raw
  member count to decide which communities get a real LLM report
  -- a small but densely-attested community can matter more than
  a larger sparse one.
- [**embedding**](#agrag-common-data_models-community-Community-embedding) (<code>list\[float\] | None</code>) – The community's dense vector, computed from title and
  summary. None before the report/embedding stage runs.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-community-Community-to_node_record) – Return this community as a GraphStore write record.

###### `agrag.common.data_models.community.Community.created_at` \{#agrag-common-data_models-community-Community-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.community.Community.embedding` \{#agrag-common-data_models-community-Community-embedding}

```python
embedding: list[float] | None = None
```

###### `agrag.common.data_models.community.Community.embedding_text` \{#agrag-common-data_models-community-Community-embedding_text}

```python
embedding_text: str
```

Return the text this community's embedding is computed from.

###### `agrag.common.data_models.community.Community.findings` \{#agrag-common-data_models-community-Community-findings}

```python
findings: list[str] = Field(default_factory=list)
```

###### `agrag.common.data_models.community.Community.id` \{#agrag-common-data_models-community-Community-id}

```python
id: UUID
```

###### `agrag.common.data_models.community.Community.internal_weight` \{#agrag-common-data_models-community-Community-internal_weight}

```python
internal_weight: float = Field(default=0.0, ge=0.0)
```

###### `agrag.common.data_models.community.Community.member_ids` \{#agrag-common-data_models-community-Community-member_ids}

```python
member_ids: list[UUID] = Field(default_factory=list)
```

###### `agrag.common.data_models.community.Community.metadata` \{#agrag-common-data_models-community-Community-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.community.Community.rating` \{#agrag-common-data_models-community-Community-rating}

```python
rating: float = Field(ge=0.0, le=10.0)
```

###### `agrag.common.data_models.community.Community.rating_explanation` \{#agrag-common-data_models-community-Community-rating_explanation}

```python
rating_explanation: str
```

###### `agrag.common.data_models.community.Community.summary` \{#agrag-common-data_models-community-Community-summary}

```python
summary: str
```

###### `agrag.common.data_models.community.Community.title` \{#agrag-common-data_models-community-Community-title}

```python
title: str
```

###### `agrag.common.data_models.community.Community.to_node_record` \{#agrag-common-data_models-community-Community-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this community as a GraphStore write record.

##### `agrag.common.data_models.community.MEMBER_OF_RELATION` \{#agrag-common-data_models-community-MEMBER_OF_RELATION}

```python
MEMBER_OF_RELATION = 'MEMBER_OF'
```

#### `agrag.common.data_models.cutover_job` \{#agrag-common-data_models-cutover_job}

Crash-recoverable state for one add/update/delete_document call.

**Classes:**

- [**CutoverJob**](#agrag-common-data_models-cutover_job-CutoverJob) – Crash-recoverable state for one add/update/delete_document call.
- [**CutoverJobStatus**](#agrag-common-data_models-cutover_job-CutoverJobStatus) – Lifecycle phase of a Cutover Job.

**Attributes:**

- [**CUTOVER_JOB_LABEL**](#agrag-common-data_models-cutover_job-CUTOVER_JOB_LABEL) –
- [**CUTOVER_JOB_STATUS_INDEX**](#agrag-common-data_models-cutover_job-CUTOVER_JOB_STATUS_INDEX) –

##### `agrag.common.data_models.cutover_job.CUTOVER_JOB_LABEL` \{#agrag-common-data_models-cutover_job-CUTOVER_JOB_LABEL}

```python
CUTOVER_JOB_LABEL = 'CutoverJob'
```

##### `agrag.common.data_models.cutover_job.CUTOVER_JOB_STATUS_INDEX` \{#agrag-common-data_models-cutover_job-CUTOVER_JOB_STATUS_INDEX}

```python
CUTOVER_JOB_STATUS_INDEX = 'cutover_job_status_index'
```

##### `agrag.common.data_models.cutover_job.CutoverJob` \{#agrag-common-data_models-cutover_job-CutoverJob}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

Crash-recoverable state for one add/update/delete_document call.

**Attributes:**

- [**document_key**](#agrag-common-data_models-cutover_job-CutoverJob-document_key) (<code>str</code>) – The document this job mutates. Unique among
  non-terminal jobs (enforced by a graph constraint plus lease
  fencing, not the constraint alone).
- [**verb**](#agrag-common-data_models-cutover_job-CutoverJob-verb) (<code>Literal['add', 'update', 'delete_document']</code>) – Which public method created this job.
- [**status**](#agrag-common-data_models-cutover_job-CutoverJob-status) (<code>[CutoverJobStatus](#agrag-common-data_models-cutover_job-CutoverJobStatus)</code>) – Current phase, see CutoverJobStatus.
- [**affected_entity_ids**](#agrag-common-data_models-cutover_job-CutoverJob-affected_entity_ids) (<code>list\[UUID\]</code>) – The snapshot taken before any pending write
  began — the only entities the cleanup phase may prune.
- [**component_seed_ids**](#agrag-common-data_models-cutover_job-CutoverJob-component_seed_ids) (<code>list\[UUID\]</code>) – One member id per match component the job
  materialized, recorded at commit. The cleanup phase rebuilds
  each component's resolved entity from these, so a resumed job
  can replace the materialization the commit left in place. Cleanup
  rebuilds these components even though they are not pruning
  candidates.
- [**lease_token**](#agrag-common-data_models-cutover_job-CutoverJob-lease_token) (<code>UUID</code>) – Current lease holder's fencing token.
- [**lease_expires_at**](#agrag-common-data_models-cutover_job-CutoverJob-lease_expires_at) (<code>datetime</code>) – When the current lease expires.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-cutover_job-CutoverJob-to_node_record) – Return this job as a graph write record.

###### `agrag.common.data_models.cutover_job.CutoverJob.affected_entity_ids` \{#agrag-common-data_models-cutover_job-CutoverJob-affected_entity_ids}

```python
affected_entity_ids: list[UUID] = Field(default_factory=list)
```

###### `agrag.common.data_models.cutover_job.CutoverJob.component_seed_ids` \{#agrag-common-data_models-cutover_job-CutoverJob-component_seed_ids}

```python
component_seed_ids: list[UUID] = Field(default_factory=list)
```

###### `agrag.common.data_models.cutover_job.CutoverJob.created_at` \{#agrag-common-data_models-cutover_job-CutoverJob-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.cutover_job.CutoverJob.document_key` \{#agrag-common-data_models-cutover_job-CutoverJob-document_key}

```python
document_key: str
```

###### `agrag.common.data_models.cutover_job.CutoverJob.id` \{#agrag-common-data_models-cutover_job-CutoverJob-id}

```python
id: UUID
```

###### `agrag.common.data_models.cutover_job.CutoverJob.lease_expires_at` \{#agrag-common-data_models-cutover_job-CutoverJob-lease_expires_at}

```python
lease_expires_at: datetime
```

###### `agrag.common.data_models.cutover_job.CutoverJob.lease_token` \{#agrag-common-data_models-cutover_job-CutoverJob-lease_token}

```python
lease_token: UUID
```

###### `agrag.common.data_models.cutover_job.CutoverJob.metadata` \{#agrag-common-data_models-cutover_job-CutoverJob-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.cutover_job.CutoverJob.status` \{#agrag-common-data_models-cutover_job-CutoverJob-status}

```python
status: CutoverJobStatus
```

###### `agrag.common.data_models.cutover_job.CutoverJob.to_node_record` \{#agrag-common-data_models-cutover_job-CutoverJob-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this job as a graph write record.

###### `agrag.common.data_models.cutover_job.CutoverJob.verb` \{#agrag-common-data_models-cutover_job-CutoverJob-verb}

```python
verb: Literal['add', 'update', 'delete_document']
```

##### `agrag.common.data_models.cutover_job.CutoverJobStatus` \{#agrag-common-data_models-cutover_job-CutoverJobStatus}

Bases: <code>StrEnum</code>

Lifecycle phase of a Cutover Job.

**Attributes:**

- [**CLEANING**](#agrag-common-data_models-cutover_job-CutoverJobStatus-CLEANING) –
- [**COMMITTED**](#agrag-common-data_models-cutover_job-CutoverJobStatus-COMMITTED) –
- [**DONE**](#agrag-common-data_models-cutover_job-CutoverJobStatus-DONE) –
- [**PENDING**](#agrag-common-data_models-cutover_job-CutoverJobStatus-PENDING) –
- [**ROLLED_BACK**](#agrag-common-data_models-cutover_job-CutoverJobStatus-ROLLED_BACK) –

###### `agrag.common.data_models.cutover_job.CutoverJobStatus.CLEANING` \{#agrag-common-data_models-cutover_job-CutoverJobStatus-CLEANING}

```python
CLEANING = 'cleaning'
```

###### `agrag.common.data_models.cutover_job.CutoverJobStatus.COMMITTED` \{#agrag-common-data_models-cutover_job-CutoverJobStatus-COMMITTED}

```python
COMMITTED = 'committed'
```

###### `agrag.common.data_models.cutover_job.CutoverJobStatus.DONE` \{#agrag-common-data_models-cutover_job-CutoverJobStatus-DONE}

```python
DONE = 'done'
```

###### `agrag.common.data_models.cutover_job.CutoverJobStatus.PENDING` \{#agrag-common-data_models-cutover_job-CutoverJobStatus-PENDING}

```python
PENDING = 'pending'
```

###### `agrag.common.data_models.cutover_job.CutoverJobStatus.ROLLED_BACK` \{#agrag-common-data_models-cutover_job-CutoverJobStatus-ROLLED_BACK}

```python
ROLLED_BACK = 'rolled_back'
```

#### `agrag.common.data_models.data_point` \{#agrag-common-data_models-data_point}

The base class for a graph node.

**Classes:**

- [**DataPoint**](#agrag-common-data_models-data_point-DataPoint) – A graph node with a fixed id and free metadata.

##### `agrag.common.data_models.data_point.DataPoint` \{#agrag-common-data_models-data_point-DataPoint}

Bases: <code>BaseModel</code>

A graph node with a fixed id and free metadata.

**Attributes:**

- [**id**](#agrag-common-data_models-data_point-DataPoint-id) (<code>UUID</code>) – The node id. Each subclass defines its own rule to compute this id.
- [**created_at**](#agrag-common-data_models-data_point-DataPoint-created_at) (<code>datetime</code>) – The time the system created this node. Defaults to the current time.
- [**metadata**](#agrag-common-data_models-data_point-DataPoint-metadata) (<code>dict\[str, Any\]</code>) – Extra data about the node. Add an `index_fields` key to list
  which fields the store must index for filters.

###### `agrag.common.data_models.data_point.DataPoint.created_at` \{#agrag-common-data_models-data_point-DataPoint-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.data_point.DataPoint.id` \{#agrag-common-data_models-data_point-DataPoint-id}

```python
id: UUID
```

###### `agrag.common.data_models.data_point.DataPoint.metadata` \{#agrag-common-data_models-data_point-DataPoint-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

#### `agrag.common.data_models.document` \{#agrag-common-data_models-document}

The Document model: one unit of source text, before chunking.

**Classes:**

- [**Document**](#agrag-common-data_models-document-Document) – One unit of source text, before chunking.
- [**DocumentFamily**](#agrag-common-data_models-document-DocumentFamily) – The shape of a document's source.
- [**HeadingRef**](#agrag-common-data_models-document-HeadingRef) – One heading in a document outline.
- [**SourceFormat**](#agrag-common-data_models-document-SourceFormat) – A source format that a loader can read.
- [**TurnRef**](#agrag-common-data_models-document-TurnRef) – One speaker turn in a chat document.

**Attributes:**

- [**DOCUMENT_LABEL**](#agrag-common-data_models-document-DOCUMENT_LABEL) –

##### `agrag.common.data_models.document.DOCUMENT_LABEL` \{#agrag-common-data_models-document-DOCUMENT_LABEL}

```python
DOCUMENT_LABEL = 'Document'
```

##### `agrag.common.data_models.document.Document` \{#agrag-common-data_models-document-Document}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

One unit of source text, before chunking.

A prose source, such as a Markdown file, makes one Document. A record source,
such as a CSV file, makes one Document per row.

The way the system computes `content_hash` depends on the loader. A text
loader hashes the decoded text. A docling loader hashes the raw source bytes
instead of the parsed output, because docling's parsed output can change
between docling versions and between runs on different hardware.

The system computes `id` from `content_hash` and `record_id` unless the caller
passes `id` directly. A record-family document without `record_id` also mixes
in `record_index` plus `source_hash`, or `uri` when `source_hash` is not
set. Pass `id` only when rebuilding a document from stored data.

**Attributes:**

- [**text**](#agrag-common-data_models-document-Document-text) (<code>str</code>) – The document text. For a docling source, this holds docling's Markdown
  export. The chunker never reads this field for a docling source; see the
  `Chunk` model for docling chunk content instead.
- [**title**](#agrag-common-data_models-document-Document-title) (<code>str</code>) – The document title.
- [**uri**](#agrag-common-data_models-document-Document-uri) (<code>str</code>) – The location of the source. This value is not part of the document id.
- [**source_format**](#agrag-common-data_models-document-Document-source_format) (<code>[SourceFormat](#agrag-common-data_models-document-SourceFormat)</code>) – The format the loader used to read this document.
- [**family**](#agrag-common-data_models-document-Document-family) (<code>[DocumentFamily](#agrag-common-data_models-document-DocumentFamily)</code>) – The shape of the source: one document per file, or one document per
  record.
- [**content_hash**](#agrag-common-data_models-document-Document-content_hash) (<code>str</code>) – The hash that forms the document id.
- [**loader_name**](#agrag-common-data_models-document-Document-loader_name) (<code>str</code>) – The name of the loader that produced this document, for example
  `"text"` or `"docling"`.
- [**loader_version**](#agrag-common-data_models-document-Document-loader_version) (<code>str | None</code>) – The version of the loader package. Does not affect the
  document id.
- [**encoding**](#agrag-common-data_models-document-Document-encoding) (<code>str | None</code>) – The text encoding. Text loaders set this field; other loaders
  leave it empty.
- [**source_hash**](#agrag-common-data_models-document-Document-source_hash) (<code>str | None</code>) – The hash of the whole source file. Record-family documents set
  this field.
- [**char_count**](#agrag-common-data_models-document-Document-char_count) (<code>int</code>) – The number of characters in `text`.
- [**line_count**](#agrag-common-data_models-document-Document-line_count) (<code>int | None</code>) – The number of lines in `text`. Some loaders do not set this field.
- [**record_index**](#agrag-common-data_models-document-Document-record_index) (<code>int | None</code>) – The 0-based row number in the source. Record-family documents
  set this field.
- [**record_id**](#agrag-common-data_models-document-Document-record_id) (<code>str | None</code>) – The value from the configured id column. Record-family documents
  set this field only when the caller configures an id column.
- [**raw_record**](#agrag-common-data_models-document-Document-raw_record) (<code>dict\[str, Any\] | None</code>) – The original record data. A loader sets this field only when the
  caller asks for it.
- [**heading_outline**](#agrag-common-data_models-document-Document-heading_outline) (<code>list\[[HeadingRef](#agrag-common-data_models-document-HeadingRef)\]</code>) – The headings in the document, with their offsets. A text
  loader sets this field for a prose document.
- [**document_key**](#agrag-common-data_models-document-Document-document_key) (<code>str | None</code>) – The stable identifier for this document's persisted graph node.
  Independent of `id`, which changes with every content edit. Defaults to
  `uri` when not supplied.
- [**turns**](#agrag-common-data_models-document-Document-turns) (<code>list\[[TurnRef](#agrag-common-data_models-document-TurnRef)\]</code>) – The speaker turns of a chat document, in order. A chat loader sets this
  field. Turn spans index `text` and do not overlap.
- [**normalization**](#agrag-common-data_models-document-Document-normalization) (<code>[Normalization](#agrag-common-data_models-normalization-Normalization) | None</code>) – How the loader normalized `text`. `None` for a document
  that no text loader made, such as a docling document or one built by hand.

**Functions:**

- [**id_for**](#agrag-common-data_models-document-Document-id_for) – Compute the document id.
- [**node_id_for**](#agrag-common-data_models-document-Document-node_id_for) – Compute the persisted Document graph node's id.
- [**to_node_record**](#agrag-common-data_models-document-Document-to_node_record) – Return this document as a GraphStore write record for its graph node.

###### `agrag.common.data_models.document.Document.char_count` \{#agrag-common-data_models-document-Document-char_count}

```python
char_count: int
```

###### `agrag.common.data_models.document.Document.content_hash` \{#agrag-common-data_models-document-Document-content_hash}

```python
content_hash: str
```

###### `agrag.common.data_models.document.Document.created_at` \{#agrag-common-data_models-document-Document-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.document.Document.document_key` \{#agrag-common-data_models-document-Document-document_key}

```python
document_key: str | None = None
```

###### `agrag.common.data_models.document.Document.encoding` \{#agrag-common-data_models-document-Document-encoding}

```python
encoding: str | None = None
```

###### `agrag.common.data_models.document.Document.family` \{#agrag-common-data_models-document-Document-family}

```python
family: DocumentFamily
```

###### `agrag.common.data_models.document.Document.heading_outline` \{#agrag-common-data_models-document-Document-heading_outline}

```python
heading_outline: list[HeadingRef] = Field(default_factory=list)
```

###### `agrag.common.data_models.document.Document.id` \{#agrag-common-data_models-document-Document-id}

```python
id: UUID | None = None
```

###### `agrag.common.data_models.document.Document.id_for` \{#agrag-common-data_models-document-Document-id_for}

```python
id_for(*, content_hash:str, record_id:str | None = None, record_index:int | None = None, source_hash:str | None = None, uri:str | None = None) -> UUID
```

Compute the document id.

A record id, when given, wins over the content hash. Without a record id,
a record-family document (`record_index` is not `None`) mixes in its
source hash and row index, so two rows with identical text but no
configured id column still get distinct ids. When the source hash is not
available, this falls back to `uri` so that two different sources still
do not collide.

**Parameters:**

- **content_hash** (<code>str</code>) – The document's content hash.
- **record_id** (<code>str | None</code>) – The value from the configured id column, when the source has one.
- **record_index** (<code>int | None</code>) – The 0-based row number, for a record-family document.
- **source_hash** (<code>str | None</code>) – The hash of the whole source file, for a record-family
  document.
- **uri** (<code>str | None</code>) – The document's source location, used in place of `source_hash`
  when the caller does not supply one.

**Returns:**

- <code>UUID</code> – The document id.

###### `agrag.common.data_models.document.Document.line_count` \{#agrag-common-data_models-document-Document-line_count}

```python
line_count: int | None = None
```

###### `agrag.common.data_models.document.Document.loader_name` \{#agrag-common-data_models-document-Document-loader_name}

```python
loader_name: str
```

###### `agrag.common.data_models.document.Document.loader_version` \{#agrag-common-data_models-document-Document-loader_version}

```python
loader_version: str | None = None
```

###### `agrag.common.data_models.document.Document.metadata` \{#agrag-common-data_models-document-Document-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.document.Document.node_id_for` \{#agrag-common-data_models-document-Document-node_id_for}

```python
node_id_for(*, document_key:str) -> UUID
```

Compute the persisted Document graph node's id.

Distinct from `id_for()`: this id is keyed on `document_key`, not the
content hash, so it stays the same across content changes to the same
logical document. Conflating the two ids would give every content version
of a document its own graph node instead of one node with a changing
content hash.

**Parameters:**

- **document_key** (<code>str</code>) – The document's stable key.

**Returns:**

- <code>UUID</code> – The Document graph node id.

###### `agrag.common.data_models.document.Document.normalization` \{#agrag-common-data_models-document-Document-normalization}

```python
normalization: Normalization | None = None
```

###### `agrag.common.data_models.document.Document.raw_record` \{#agrag-common-data_models-document-Document-raw_record}

```python
raw_record: dict[str, Any] | None = None
```

###### `agrag.common.data_models.document.Document.record_id` \{#agrag-common-data_models-document-Document-record_id}

```python
record_id: str | None = None
```

###### `agrag.common.data_models.document.Document.record_index` \{#agrag-common-data_models-document-Document-record_index}

```python
record_index: int | None = None
```

###### `agrag.common.data_models.document.Document.resolved_document_key` \{#agrag-common-data_models-document-Document-resolved_document_key}

```python
resolved_document_key: str
```

The document key, guaranteed non-`None` once construction succeeds.

`document_key` is typed as optional because callers may omit it and let
`_resolve_document_key` default it to `uri`, but every constructed
`Document` has a non-`None` document key by the time callers see it. Use
this property instead of `document_key` where a non-optional value is
required, such as computing the persisted Document node's id.

**Raises:**

- <code>RuntimeError</code> – `document_key` is still `None`, which means a validator
  was bypassed, for example via `model_construct`.

###### `agrag.common.data_models.document.Document.resolved_id` \{#agrag-common-data_models-document-Document-resolved_id}

```python
resolved_id: UUID
```

The document id, guaranteed non-`None` once construction succeeds.

`id` is typed as optional because callers may omit it and let
`_resolve_id` derive it, but every constructed `Document` has a
non-`None` id by the time callers see it. Use this property instead of
`id` where a non-optional value is required, such as building a `Chunk`.

**Raises:**

- <code>RuntimeError</code> – `id` is still `None`, which means a validator was
  bypassed, for example via `model_construct`.

###### `agrag.common.data_models.document.Document.source_format` \{#agrag-common-data_models-document-Document-source_format}

```python
source_format: SourceFormat
```

###### `agrag.common.data_models.document.Document.source_hash` \{#agrag-common-data_models-document-Document-source_hash}

```python
source_hash: str | None = None
```

###### `agrag.common.data_models.document.Document.text` \{#agrag-common-data_models-document-Document-text}

```python
text: str
```

###### `agrag.common.data_models.document.Document.title` \{#agrag-common-data_models-document-Document-title}

```python
title: str
```

###### `agrag.common.data_models.document.Document.to_node_record` \{#agrag-common-data_models-document-Document-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this document as a GraphStore write record for its graph node.

The record excludes `text`: the persisted node exists for traversal and
the update no-op check, not to duplicate the document body already held
per-chunk.

###### `agrag.common.data_models.document.Document.turns` \{#agrag-common-data_models-document-Document-turns}

```python
turns: list[TurnRef] = Field(default_factory=list)
```

###### `agrag.common.data_models.document.Document.uri` \{#agrag-common-data_models-document-Document-uri}

```python
uri: str
```

##### `agrag.common.data_models.document.DocumentFamily` \{#agrag-common-data_models-document-DocumentFamily}

Bases: <code>StrEnum</code>

The shape of a document's source.

**Attributes:**

- [**PROSE**](#agrag-common-data_models-document-DocumentFamily-PROSE) – One source file makes one document.
- [**RECORD**](#agrag-common-data_models-document-DocumentFamily-RECORD) – One source file makes many documents, one per record.

###### `agrag.common.data_models.document.DocumentFamily.PROSE` \{#agrag-common-data_models-document-DocumentFamily-PROSE}

```python
PROSE = 'prose'
```

###### `agrag.common.data_models.document.DocumentFamily.RECORD` \{#agrag-common-data_models-document-DocumentFamily-RECORD}

```python
RECORD = 'record'
```

##### `agrag.common.data_models.document.HeadingRef` \{#agrag-common-data_models-document-HeadingRef}

Bases: <code>BaseModel</code>

One heading in a document outline.

**Attributes:**

- [**text**](#agrag-common-data_models-document-HeadingRef-text) (<code>str</code>) – The heading text.
- [**level**](#agrag-common-data_models-document-HeadingRef-level) (<code>int</code>) – The heading depth. A top-level heading has level 1.
- [**char_start**](#agrag-common-data_models-document-HeadingRef-char_start) (<code>int</code>) – The start character offset of the heading in the document text. The
  chunker uses this offset to find which heading contains each chunk, since
  the
  base chunker does not detect headings on its own.

###### `agrag.common.data_models.document.HeadingRef.char_start` \{#agrag-common-data_models-document-HeadingRef-char_start}

```python
char_start: int
```

###### `agrag.common.data_models.document.HeadingRef.level` \{#agrag-common-data_models-document-HeadingRef-level}

```python
level: int
```

###### `agrag.common.data_models.document.HeadingRef.text` \{#agrag-common-data_models-document-HeadingRef-text}

```python
text: str
```

##### `agrag.common.data_models.document.SourceFormat` \{#agrag-common-data_models-document-SourceFormat}

Bases: <code>StrEnum</code>

A source format that a loader can read.

The field that holds this value is named `source_format`, not `format`.
`format`
is a Python builtin, and this project's lint rules reject builtin names for fields.

**Attributes:**

- [**ASCIIDOC**](#agrag-common-data_models-document-SourceFormat-ASCIIDOC) –
- [**CSV**](#agrag-common-data_models-document-SourceFormat-CSV) –
- [**DOCX**](#agrag-common-data_models-document-SourceFormat-DOCX) –
- [**HTML**](#agrag-common-data_models-document-SourceFormat-HTML) –
- [**IMAGE**](#agrag-common-data_models-document-SourceFormat-IMAGE) –
- [**JSON**](#agrag-common-data_models-document-SourceFormat-JSON) –
- [**JSONL**](#agrag-common-data_models-document-SourceFormat-JSONL) –
- [**LOG**](#agrag-common-data_models-document-SourceFormat-LOG) –
- [**MARKDOWN**](#agrag-common-data_models-document-SourceFormat-MARKDOWN) –
- [**PDF**](#agrag-common-data_models-document-SourceFormat-PDF) –
- [**PPTX**](#agrag-common-data_models-document-SourceFormat-PPTX) –
- [**TSV**](#agrag-common-data_models-document-SourceFormat-TSV) –
- [**TXT**](#agrag-common-data_models-document-SourceFormat-TXT) –
- [**XML**](#agrag-common-data_models-document-SourceFormat-XML) –

###### `agrag.common.data_models.document.SourceFormat.ASCIIDOC` \{#agrag-common-data_models-document-SourceFormat-ASCIIDOC}

```python
ASCIIDOC = 'asciidoc'
```

###### `agrag.common.data_models.document.SourceFormat.CSV` \{#agrag-common-data_models-document-SourceFormat-CSV}

```python
CSV = 'csv'
```

###### `agrag.common.data_models.document.SourceFormat.DOCX` \{#agrag-common-data_models-document-SourceFormat-DOCX}

```python
DOCX = 'docx'
```

###### `agrag.common.data_models.document.SourceFormat.HTML` \{#agrag-common-data_models-document-SourceFormat-HTML}

```python
HTML = 'html'
```

###### `agrag.common.data_models.document.SourceFormat.IMAGE` \{#agrag-common-data_models-document-SourceFormat-IMAGE}

```python
IMAGE = 'image'
```

###### `agrag.common.data_models.document.SourceFormat.JSON` \{#agrag-common-data_models-document-SourceFormat-JSON}

```python
JSON = 'json'
```

###### `agrag.common.data_models.document.SourceFormat.JSONL` \{#agrag-common-data_models-document-SourceFormat-JSONL}

```python
JSONL = 'jsonl'
```

###### `agrag.common.data_models.document.SourceFormat.LOG` \{#agrag-common-data_models-document-SourceFormat-LOG}

```python
LOG = 'log'
```

###### `agrag.common.data_models.document.SourceFormat.MARKDOWN` \{#agrag-common-data_models-document-SourceFormat-MARKDOWN}

```python
MARKDOWN = 'markdown'
```

###### `agrag.common.data_models.document.SourceFormat.PDF` \{#agrag-common-data_models-document-SourceFormat-PDF}

```python
PDF = 'pdf'
```

###### `agrag.common.data_models.document.SourceFormat.PPTX` \{#agrag-common-data_models-document-SourceFormat-PPTX}

```python
PPTX = 'pptx'
```

###### `agrag.common.data_models.document.SourceFormat.TSV` \{#agrag-common-data_models-document-SourceFormat-TSV}

```python
TSV = 'tsv'
```

###### `agrag.common.data_models.document.SourceFormat.TXT` \{#agrag-common-data_models-document-SourceFormat-TXT}

```python
TXT = 'txt'
```

###### `agrag.common.data_models.document.SourceFormat.XML` \{#agrag-common-data_models-document-SourceFormat-XML}

```python
XML = 'xml'
```

##### `agrag.common.data_models.document.TurnRef` \{#agrag-common-data_models-document-TurnRef}

Bases: <code>BaseModel</code>

One speaker turn in a chat document.

**Attributes:**

- [**role**](#agrag-common-data_models-document-TurnRef-role) (<code>str</code>) – The speaker of the turn, for example `"user"`.
- [**turn_id**](#agrag-common-data_models-document-TurnRef-turn_id) (<code>str | None</code>) – The id of the message in the source, when it has one.
- [**char_start**](#agrag-common-data_models-document-TurnRef-char_start) (<code>int</code>) – The start character offset of the turn in the document text.
- [**char_end**](#agrag-common-data_models-document-TurnRef-char_end) (<code>int</code>) – The end character offset of the turn, exclusive.

###### `agrag.common.data_models.document.TurnRef.char_end` \{#agrag-common-data_models-document-TurnRef-char_end}

```python
char_end: int
```

###### `agrag.common.data_models.document.TurnRef.char_start` \{#agrag-common-data_models-document-TurnRef-char_start}

```python
char_start: int
```

###### `agrag.common.data_models.document.TurnRef.role` \{#agrag-common-data_models-document-TurnRef-role}

```python
role: str = Field(min_length=1)
```

###### `agrag.common.data_models.document.TurnRef.turn_id` \{#agrag-common-data_models-document-TurnRef-turn_id}

```python
turn_id: str | None = None
```

#### `agrag.common.data_models.entity` \{#agrag-common-data_models-entity}

A permanent mention-level graph node, accumulated by exact-name matching.

**Classes:**

- [**Entity**](#agrag-common-data_models-entity-Entity) – A permanent mention-level node, never destroyed once written.

##### `agrag.common.data_models.entity.Entity` \{#agrag-common-data_models-entity-Entity}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A permanent mention-level node, never destroyed once written.

Each Entity is one raw record: exact-match accumulation only folds a
new mention into the existing node for its normalized name. Fuzzy,
embedding, and LLM matches never absorb a node; they persist as
MATCHES edges with a derived ResolvedEntity instead, so both raw
records and their relationships survive resolution.

**Attributes:**

- [**label**](#agrag-common-data_models-entity-Entity-label) (<code>str</code>) – The EntityType label this entity was resolved as.
- [**name**](#agrag-common-data_models-entity-Entity-name) (<code>str</code>) – The canonical resolved surface form — field-resolved the same
  way any property is, but kept as its own field rather than
  inside properties, since every entity has one regardless of
  EntityType.properties' schema, and it is what gets embedded
  (embedding_text).
- [**properties**](#agrag-common-data_models-entity-Entity-properties) (<code>dict\[str, object\]</code>) – Field-resolved property values, keyed by the schema's
  declared property names (e.g. "dosage", "description" — whatever
  EntityType.properties for this label declares). Never holds name.
- [**embedding**](#agrag-common-data_models-entity-Entity-embedding) (<code>list\[float\] | None</code>) – The entity's dense vector, once populated by the storage
  stage. None before that point.
- [**merge_count**](#agrag-common-data_models-entity-Entity-merge_count) (<code>int</code>) – The total number of source mentions this entity's data
  was assembled from. Starts at 1.
- [**source_chunk_ids**](#agrag-common-data_models-entity-Entity-source_chunk_ids) (<code>list\[UUID\]</code>) – Ids of every Chunk a mention contributing to this
  entity's data came from. Each also backs one MENTIONED_IN edge
  from that Chunk to this Entity.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-entity-Entity-to_node_record) – Return this entity as a GraphStore write record.

###### `agrag.common.data_models.entity.Entity.created_at` \{#agrag-common-data_models-entity-Entity-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.entity.Entity.embedding` \{#agrag-common-data_models-entity-Entity-embedding}

```python
embedding: list[float] | None = None
```

###### `agrag.common.data_models.entity.Entity.embedding_text` \{#agrag-common-data_models-entity-Entity-embedding_text}

```python
embedding_text: str
```

Return the text this entity's embedding is computed from.

Name alone, or name plus a "description" property when the schema
declares one — decided once, here, so every embedding call site
(resolution's future embedding tier, storage-stage population,
Graph.consolidate()) embeds the same text for the same entity.

###### `agrag.common.data_models.entity.Entity.id` \{#agrag-common-data_models-entity-Entity-id}

```python
id: UUID
```

###### `agrag.common.data_models.entity.Entity.label` \{#agrag-common-data_models-entity-Entity-label}

```python
label: str
```

###### `agrag.common.data_models.entity.Entity.merge_count` \{#agrag-common-data_models-entity-Entity-merge_count}

```python
merge_count: int = 1
```

###### `agrag.common.data_models.entity.Entity.merge_key` \{#agrag-common-data_models-entity-Entity-merge_key}

```python
merge_key: str
```

Return this entity's global exact-match lookup key.

(label, normalized name) — the same identity ExactMatch already uses
in-batch, applied to a persisted store lookup. A derived value, not
stored redundantly anywhere else on this model; to_node_record()
computes it fresh from label/name every write, so it can never drift
from what the fields it's derived from actually say.

###### `agrag.common.data_models.entity.Entity.metadata` \{#agrag-common-data_models-entity-Entity-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.entity.Entity.name` \{#agrag-common-data_models-entity-Entity-name}

```python
name: str
```

###### `agrag.common.data_models.entity.Entity.properties` \{#agrag-common-data_models-entity-Entity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

###### `agrag.common.data_models.entity.Entity.source_chunk_ids` \{#agrag-common-data_models-entity-Entity-source_chunk_ids}

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

###### `agrag.common.data_models.entity.Entity.to_node_record` \{#agrag-common-data_models-entity-Entity-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this entity as a GraphStore write record.

Name, merge_key, merge_count, and source_chunk_ids are
flattened into properties as plain JSON-safe values; GraphStore has
no reason to know these fields are special.

#### `agrag.common.data_models.extraction` \{#agrag-common-data_models-extraction}

Pre-resolution entity and relation mentions produced by an Extractor.

**Classes:**

- [**ExtractedEntity**](#agrag-common-data_models-extraction-ExtractedEntity) – One entity mention found in a single Chunk.
- [**ExtractedRelation**](#agrag-common-data_models-extraction-ExtractedRelation) – One relation mention between two ExtractedEntity mentions in one Chunk.
- [**ExtractionResult**](#agrag-common-data_models-extraction-ExtractionResult) – The entities and relations one Extractor call found in one Chunk.

##### `agrag.common.data_models.extraction.ExtractedEntity` \{#agrag-common-data_models-extraction-ExtractedEntity}

Bases: <code>BaseModel</code>

One entity mention found in a single Chunk.

Not a graph node: this has no id and no canonical identity. Resolution decides
which ExtractedEntity mentions refer to the same real-world thing.

**Attributes:**

- [**chunk_id**](#agrag-common-data_models-extraction-ExtractedEntity-chunk_id) (<code>UUID</code>) – The id of the Chunk this mention came from.
- [**label**](#agrag-common-data_models-extraction-ExtractedEntity-label) (<code>str</code>) – The EntityType label this mention was extracted as.
- [**text**](#agrag-common-data_models-extraction-ExtractedEntity-text) (<code>str</code>) – The mention's surface text.
- [**char_start**](#agrag-common-data_models-extraction-ExtractedEntity-char_start) (<code>int</code>) – The start character offset within the chunk's text.
- [**char_end**](#agrag-common-data_models-extraction-ExtractedEntity-char_end) (<code>int</code>) – The end character offset within the chunk's text.
- [**confidence**](#agrag-common-data_models-extraction-ExtractedEntity-confidence) (<code>float | None</code>) – The extractor's confidence in this mention, when available.
- [**properties**](#agrag-common-data_models-extraction-ExtractedEntity-properties) (<code>dict\[str, object\]</code>) – Schema-declared property values this mention carries,
  keyed by property name. Empty for an extractor that only reports
  spans -- normalize_extraction_result drops any key the schema
  does not declare for this mention's label.

###### `agrag.common.data_models.extraction.ExtractedEntity.char_end` \{#agrag-common-data_models-extraction-ExtractedEntity-char_end}

```python
char_end: int
```

###### `agrag.common.data_models.extraction.ExtractedEntity.char_start` \{#agrag-common-data_models-extraction-ExtractedEntity-char_start}

```python
char_start: int
```

###### `agrag.common.data_models.extraction.ExtractedEntity.chunk_id` \{#agrag-common-data_models-extraction-ExtractedEntity-chunk_id}

```python
chunk_id: UUID
```

###### `agrag.common.data_models.extraction.ExtractedEntity.confidence` \{#agrag-common-data_models-extraction-ExtractedEntity-confidence}

```python
confidence: float | None = None
```

###### `agrag.common.data_models.extraction.ExtractedEntity.label` \{#agrag-common-data_models-extraction-ExtractedEntity-label}

```python
label: str
```

###### `agrag.common.data_models.extraction.ExtractedEntity.properties` \{#agrag-common-data_models-extraction-ExtractedEntity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

###### `agrag.common.data_models.extraction.ExtractedEntity.text` \{#agrag-common-data_models-extraction-ExtractedEntity-text}

```python
text: str
```

##### `agrag.common.data_models.extraction.ExtractedRelation` \{#agrag-common-data_models-extraction-ExtractedRelation}

Bases: <code>BaseModel</code>

One relation mention between two ExtractedEntity mentions in one Chunk.

**Attributes:**

- [**chunk_id**](#agrag-common-data_models-extraction-ExtractedRelation-chunk_id) (<code>UUID</code>) – The id of the Chunk this mention came from.
- [**label**](#agrag-common-data_models-extraction-ExtractedRelation-label) (<code>str</code>) – The RelationType label this mention was extracted as.
- [**source_index**](#agrag-common-data_models-extraction-ExtractedRelation-source_index) (<code>int</code>) – Index of the source entity in the same ExtractionResult.entities.
- [**target_index**](#agrag-common-data_models-extraction-ExtractedRelation-target_index) (<code>int</code>) – Index of the target entity in the same ExtractionResult.entities.
- [**confidence**](#agrag-common-data_models-extraction-ExtractedRelation-confidence) (<code>float | None</code>) – The extractor's confidence in this mention, when available.

###### `agrag.common.data_models.extraction.ExtractedRelation.chunk_id` \{#agrag-common-data_models-extraction-ExtractedRelation-chunk_id}

```python
chunk_id: UUID
```

###### `agrag.common.data_models.extraction.ExtractedRelation.confidence` \{#agrag-common-data_models-extraction-ExtractedRelation-confidence}

```python
confidence: float | None = None
```

###### `agrag.common.data_models.extraction.ExtractedRelation.label` \{#agrag-common-data_models-extraction-ExtractedRelation-label}

```python
label: str
```

###### `agrag.common.data_models.extraction.ExtractedRelation.source_index` \{#agrag-common-data_models-extraction-ExtractedRelation-source_index}

```python
source_index: int
```

###### `agrag.common.data_models.extraction.ExtractedRelation.target_index` \{#agrag-common-data_models-extraction-ExtractedRelation-target_index}

```python
target_index: int
```

##### `agrag.common.data_models.extraction.ExtractionResult` \{#agrag-common-data_models-extraction-ExtractionResult}

Bases: <code>BaseModel</code>

The entities and relations one Extractor call found in one Chunk.

**Attributes:**

- [**entities**](#agrag-common-data_models-extraction-ExtractionResult-entities) (<code>list\[[ExtractedEntity](#agrag-common-data_models-extraction-ExtractedEntity)\]</code>) – The mentions found, in extraction order.
- [**relations**](#agrag-common-data_models-extraction-ExtractionResult-relations) (<code>list\[[ExtractedRelation](#agrag-common-data_models-extraction-ExtractedRelation)\]</code>) – The relation mentions found, referencing entities by index.
- [**extractor_name**](#agrag-common-data_models-extraction-ExtractionResult-extractor_name) (<code>str</code>) – Which Extractor produced this result. Set by the Extractor
  itself; useful for provenance when a EscalatingExtractor escalated.

###### `agrag.common.data_models.extraction.ExtractionResult.entities` \{#agrag-common-data_models-extraction-ExtractionResult-entities}

```python
entities: list[ExtractedEntity]
```

###### `agrag.common.data_models.extraction.ExtractionResult.extractor_name` \{#agrag-common-data_models-extraction-ExtractionResult-extractor_name}

```python
extractor_name: str
```

###### `agrag.common.data_models.extraction.ExtractionResult.relations` \{#agrag-common-data_models-extraction-ExtractionResult-relations}

```python
relations: list[ExtractedRelation]
```

#### `agrag.common.data_models.graph_record` \{#agrag-common-data_models-graph_record}

Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity/Relation
domain model resolution will eventually produce. See the future
storage/merge-mechanics work this decouples from.

Pending-visibility convention: a node or edge *created* by an in-flight
Cutover Job carries `_pending_job_id` (the job's id) in its properties;
committed data never carries this key. Retrieval query builders exclude
such rows with `pending_filter_clause`. Vector-store payloads mirror the
tag as an explicit boolean `_pending` field, cleared at commit, because
payload filters match on present values rather than key absence.

The tag is written with `ON CREATE SET`, so a job that writes over a
row that already exists leaves it untagged. Such a row was already
visible before the job started and stays visible; the job's rollback,
which deletes tagged rows, therefore cannot delete data a caller
committed earlier.

**Classes:**

- [**NodeRecord**](#agrag-common-data_models-graph_record-NodeRecord) – One graph node, ready to write.
- [**RelationRecord**](#agrag-common-data_models-graph_record-RelationRecord) – One graph relationship, ready to write.
- [**UpsertFailure**](#agrag-common-data_models-graph_record-UpsertFailure) – One record that failed to write within a bulk upsert call.
- [**UpsertResult**](#agrag-common-data_models-graph_record-UpsertResult) – Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

**Functions:**

- [**tag_pending**](#agrag-common-data_models-graph_record-tag_pending) – Stamp a write record with the Cutover Job that is writing it.

**Attributes:**

- [**PENDING_JOB_ID_PROPERTY**](#agrag-common-data_models-graph_record-PENDING_JOB_ID_PROPERTY) – Graph property marking a node or edge as created by an in-flight job.

##### `agrag.common.data_models.graph_record.NodeRecord` \{#agrag-common-data_models-graph_record-NodeRecord}

Bases: <code>BaseModel</code>

One graph node, ready to write.

**Attributes:**

- [**id**](#agrag-common-data_models-graph_record-NodeRecord-id) (<code>UUID</code>) – The node id.
- [**labels**](#agrag-common-data_models-graph_record-NodeRecord-labels) (<code>list\[str\]</code>) – The node's labels. A node carries every label listed here;
  `GraphStore.upsert_nodes` groups records by their full label set
  within a batch, since Cypher requires labels to be literal in the
  query rather than a runtime parameter.
- [**properties**](#agrag-common-data_models-graph_record-NodeRecord-properties) (<code>dict\[str, Any\]</code>) – The node's properties, including an embedding vector under
  whatever key `GraphStore.ensure_vector_index` was configured
  with, if native vector search is in use.

**Functions:**

- [**reject_pending_tag**](#agrag-common-data_models-graph_record-NodeRecord-reject_pending_tag) – Reject the job-owned tag in external graph records.

###### `agrag.common.data_models.graph_record.NodeRecord.id` \{#agrag-common-data_models-graph_record-NodeRecord-id}

```python
id: UUID
```

###### `agrag.common.data_models.graph_record.NodeRecord.labels` \{#agrag-common-data_models-graph_record-NodeRecord-labels}

```python
labels: list[str] = Field(min_length=1)
```

###### `agrag.common.data_models.graph_record.NodeRecord.properties` \{#agrag-common-data_models-graph_record-NodeRecord-properties}

```python
properties: dict[str, Any]
```

###### `agrag.common.data_models.graph_record.NodeRecord.reject_pending_tag` \{#agrag-common-data_models-graph_record-NodeRecord-reject_pending_tag}

```python
reject_pending_tag(properties:dict[str, Any]) -> dict[str, Any]
```

Reject the job-owned tag in external graph records.

##### `agrag.common.data_models.graph_record.PENDING_JOB_ID_PROPERTY` \{#agrag-common-data_models-graph_record-PENDING_JOB_ID_PROPERTY}

```python
PENDING_JOB_ID_PROPERTY = '_pending_job_id'
```

Graph property marking a node or edge as created by an in-flight job.

Carried on every node or edge a Cutover Job creates; committed data and
rows a job only writes over never carry it. Retrieval query builders
exclude rows carrying it, the commit step removes it atomically, and
rollback deletes every row carrying it. Vector-store payloads mirror it
under the same key for commit-time clearing.

##### `agrag.common.data_models.graph_record.RelationRecord` \{#agrag-common-data_models-graph_record-RelationRecord}

Bases: <code>BaseModel</code>

One graph relationship, ready to write.

**Attributes:**

- [**id**](#agrag-common-data_models-graph_record-RelationRecord-id) (<code>UUID</code>) – The relationship id.
- [**type**](#agrag-common-data_models-graph_record-RelationRecord-type) (<code>str</code>) – The relationship type.
- [**start_id**](#agrag-common-data_models-graph_record-RelationRecord-start_id) (<code>UUID</code>) – The id of the start node.
- [**end_id**](#agrag-common-data_models-graph_record-RelationRecord-end_id) (<code>UUID</code>) – The id of the end node.
- [**properties**](#agrag-common-data_models-graph_record-RelationRecord-properties) (<code>dict\[str, Any\]</code>) – The relationship's properties.

**Functions:**

- [**reject_pending_tag**](#agrag-common-data_models-graph_record-RelationRecord-reject_pending_tag) – Reject the job-owned tag in external graph records.

###### `agrag.common.data_models.graph_record.RelationRecord.end_id` \{#agrag-common-data_models-graph_record-RelationRecord-end_id}

```python
end_id: UUID
```

###### `agrag.common.data_models.graph_record.RelationRecord.id` \{#agrag-common-data_models-graph_record-RelationRecord-id}

```python
id: UUID
```

###### `agrag.common.data_models.graph_record.RelationRecord.properties` \{#agrag-common-data_models-graph_record-RelationRecord-properties}

```python
properties: dict[str, Any]
```

###### `agrag.common.data_models.graph_record.RelationRecord.reject_pending_tag` \{#agrag-common-data_models-graph_record-RelationRecord-reject_pending_tag}

```python
reject_pending_tag(properties:dict[str, Any]) -> dict[str, Any]
```

Reject the job-owned tag in external graph records.

###### `agrag.common.data_models.graph_record.RelationRecord.start_id` \{#agrag-common-data_models-graph_record-RelationRecord-start_id}

```python
start_id: UUID
```

###### `agrag.common.data_models.graph_record.RelationRecord.type` \{#agrag-common-data_models-graph_record-RelationRecord-type}

```python
type: str
```

##### `agrag.common.data_models.graph_record.UpsertFailure` \{#agrag-common-data_models-graph_record-UpsertFailure}

Bases: <code>BaseModel</code>

One record that failed to write within a bulk upsert call.

**Attributes:**

- [**id**](#agrag-common-data_models-graph_record-UpsertFailure-id) (<code>str</code>) – The failed record's own id, as a string (matches the id already
  sent to the backend, not necessarily parseable back to UUID for
  every future backend).
- [**error_type**](#agrag-common-data_models-graph_record-UpsertFailure-error_type) (<code>str</code>) – The backend exception class name or GraphStore failure label.
- [**error_message**](#agrag-common-data_models-graph_record-UpsertFailure-error_message) (<code>str</code>) – The backend exception message or failure description.

###### `agrag.common.data_models.graph_record.UpsertFailure.error_message` \{#agrag-common-data_models-graph_record-UpsertFailure-error_message}

```python
error_message: str
```

###### `agrag.common.data_models.graph_record.UpsertFailure.error_type` \{#agrag-common-data_models-graph_record-UpsertFailure-error_type}

```python
error_type: str
```

###### `agrag.common.data_models.graph_record.UpsertFailure.id` \{#agrag-common-data_models-graph_record-UpsertFailure-id}

```python
id: str
```

##### `agrag.common.data_models.graph_record.UpsertResult` \{#agrag-common-data_models-graph_record-UpsertResult}

Bases: <code>BaseModel</code>

Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

**Attributes:**

- [**written**](#agrag-common-data_models-graph_record-UpsertResult-written) (<code>int</code>) – How many records were written successfully.
- [**failures**](#agrag-common-data_models-graph_record-UpsertResult-failures) (<code>list\[[UpsertFailure](#agrag-common-data_models-graph_record-UpsertFailure)\]</code>) – Records that failed, isolated from the rest of the call.
  Empty when every record wrote successfully.

###### `agrag.common.data_models.graph_record.UpsertResult.failures` \{#agrag-common-data_models-graph_record-UpsertResult-failures}

```python
failures: list[UpsertFailure] = Field(default_factory=list)
```

###### `agrag.common.data_models.graph_record.UpsertResult.written` \{#agrag-common-data_models-graph_record-UpsertResult-written}

```python
written: int = 0
```

##### `agrag.common.data_models.graph_record.tag_pending` \{#agrag-common-data_models-graph_record-tag_pending}

```python
tag_pending(record:_RecordT, job_id:UUID | str | None) -> _RecordT
```

Stamp a write record with the Cutover Job that is writing it.

The tag reaches the graph only when the write creates its row; the
upsert queries apply it with `ON CREATE SET`.

No-op outside a job, so pipeline stages thread their optional job id
through this unconditionally instead of branching at every write.

**Parameters:**

- **record** (<code>\_RecordT</code>) – The node or relationship record about to be written.
- **job_id** (<code>UUID | str | None</code>) – The in-flight job's id, or None outside a job.

**Returns:**

- <code>\_RecordT</code> – A tagged copy when a job id was given; otherwise the original record.

#### `agrag.common.data_models.graph_schema` \{#agrag-common-data_models-graph_schema}

The GraphSchema contract: entity and relation types extraction validates against.

**Classes:**

- [**EntityType**](#agrag-common-data_models-graph_schema-EntityType) – One kind of entity a schema recognizes.
- [**GraphSchema**](#agrag-common-data_models-graph_schema-GraphSchema) – A versioned contract of entity and relation types.
- [**RelationType**](#agrag-common-data_models-graph_schema-RelationType) – One kind of relation a schema recognizes.

**Attributes:**

- [**GENERIC**](#agrag-common-data_models-graph_schema-GENERIC) – A ready-made schema for open-domain text.

##### `agrag.common.data_models.graph_schema.EntityType` \{#agrag-common-data_models-graph_schema-EntityType}

Bases: <code>BaseModel</code>

One kind of entity a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-graph_schema-EntityType-label) (<code>str</code>) – The node label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-graph_schema-EntityType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**properties**](#agrag-common-data_models-graph_schema-EntityType-properties) (<code>dict\[str, str\]</code>) – Property names mapped to a type name, such as `"str"` or
  `"date"`. `label` and `text` are rejected, since both are
  vector payload keys retrieval filtering and keyword search use.
- [**subtypes**](#agrag-common-data_models-graph_schema-EntityType-subtypes) (<code>list\[str\]</code>) – Labels that narrow this type. Empty when this type has no subtypes.

###### `agrag.common.data_models.graph_schema.EntityType.description` \{#agrag-common-data_models-graph_schema-EntityType-description}

```python
description: str
```

###### `agrag.common.data_models.graph_schema.EntityType.label` \{#agrag-common-data_models-graph_schema-EntityType-label}

```python
label: str
```

###### `agrag.common.data_models.graph_schema.EntityType.properties` \{#agrag-common-data_models-graph_schema-EntityType-properties}

```python
properties: dict[str, str] = Field(default_factory=dict)
```

###### `agrag.common.data_models.graph_schema.EntityType.subtypes` \{#agrag-common-data_models-graph_schema-EntityType-subtypes}

```python
subtypes: list[str] = Field(default_factory=list)
```

##### `agrag.common.data_models.graph_schema.GENERIC` \{#agrag-common-data_models-graph_schema-GENERIC}

```python
GENERIC = GraphSchema(name='generic', version='1', entities=[EntityType(label='Person', description='A named individual.'), EntityType(label='Organization', description='A company or institution.'), EntityType(label='Location', description='A place or geographic area.'), EntityType(label='Event', description='A named occurrence at a time or place.'), EntityType(label='Product', description='A named product, service, or work.')], relations=[RelationType(label='RELATED_TO', description='A generic relationship between two entities.', patterns=[(src, tgt) for src in _GENERIC_LABELS for tgt in _GENERIC_LABELS])])
```

A ready-made schema for open-domain text.

It declares five entity types (`Person`, `Organization`, `Location`,
`Event`, and `Product`) and one relation, `RELATED_TO`, allowed between any
two of them. Use it to try agrag without writing a schema.

##### `agrag.common.data_models.graph_schema.GraphSchema` \{#agrag-common-data_models-graph_schema-GraphSchema}

Bases: <code>BaseModel</code>

A versioned contract of entity and relation types.

Every extraction call is validated against a GraphSchema; there is no schema-free
extraction path. Round-trip with `model_dump(mode="json")`/`model_validate()`.
A schema declaring an entity property name the vector payload reserves fails that
validation, so a payload written before the check existed must be migrated before
it loads again. See `EntityType.properties`.

**Attributes:**

- [**name**](#agrag-common-data_models-graph_schema-GraphSchema-name) (<code>str</code>) – A short, unique name for this schema.
- [**version**](#agrag-common-data_models-graph_schema-GraphSchema-version) (<code>str</code>) – The schema version. Bump when types or patterns change.
- [**entities**](#agrag-common-data_models-graph_schema-GraphSchema-entities) (<code>list\[[EntityType](#agrag-common-data_models-graph_schema-EntityType)\]</code>) – The entity types this schema recognizes.
- [**relations**](#agrag-common-data_models-graph_schema-GraphSchema-relations) (<code>list\[[RelationType](#agrag-common-data_models-graph_schema-RelationType)\]</code>) – The relation types this schema recognizes.

**Functions:**

- [**to_compact_summary**](#agrag-common-data_models-graph_schema-GraphSchema-to_compact_summary) – Serialize only entity labels and relation patterns for a prompt.
- [**to_prompt_description**](#agrag-common-data_models-graph_schema-GraphSchema-to_prompt_description) – Serialize this schema in full for an LLM prompt.

###### `agrag.common.data_models.graph_schema.GraphSchema.entities` \{#agrag-common-data_models-graph_schema-GraphSchema-entities}

```python
entities: list[EntityType]
```

###### `agrag.common.data_models.graph_schema.GraphSchema.name` \{#agrag-common-data_models-graph_schema-GraphSchema-name}

```python
name: str
```

###### `agrag.common.data_models.graph_schema.GraphSchema.relations` \{#agrag-common-data_models-graph_schema-GraphSchema-relations}

```python
relations: list[RelationType]
```

###### `agrag.common.data_models.graph_schema.GraphSchema.to_compact_summary` \{#agrag-common-data_models-graph_schema-GraphSchema-to_compact_summary}

```python
to_compact_summary() -> str
```

Serialize only entity labels and relation patterns for a prompt.

Descriptions, properties, and subtypes are omitted, so this is the
shape to inject where prompt space is tight.
:meth:`to_prompt_description` carries the same labels with their
full detail.

**Returns:**

- <code>str</code> – A plain-text summary of entity labels and valid relation
- <code>str</code> – patterns.

###### `agrag.common.data_models.graph_schema.GraphSchema.to_prompt_description` \{#agrag-common-data_models-graph_schema-GraphSchema-to_prompt_description}

```python
to_prompt_description() -> str
```

Serialize this schema in full for an LLM prompt.

Every entity type's label, description, declared properties, and
subtypes are listed, followed by every relation type's label,
description, and valid (source, target) patterns. Use
:meth:`to_compact_summary` instead when prompt space is tight.

**Returns:**

- <code>str</code> – A plain-text schema description, one fact per line.

###### `agrag.common.data_models.graph_schema.GraphSchema.version` \{#agrag-common-data_models-graph_schema-GraphSchema-version}

```python
version: str
```

##### `agrag.common.data_models.graph_schema.RelationType` \{#agrag-common-data_models-graph_schema-RelationType}

Bases: <code>BaseModel</code>

One kind of relation a schema recognizes.

**Attributes:**

- [**label**](#agrag-common-data_models-graph_schema-RelationType-label) (<code>str</code>) – The relation label used in the extraction prompt and the graph.
- [**description**](#agrag-common-data_models-graph_schema-RelationType-description) (<code>str</code>) – Guidance fed to the extractor prompt or schema builder.
- [**patterns**](#agrag-common-data_models-graph_schema-RelationType-patterns) (<code>list\[tuple\[str, str\]\]</code>) – Valid (source_label, target_label) pairs for this relation. An
  extraction whose triple is not in this list is dropped at normalize time.

###### `agrag.common.data_models.graph_schema.RelationType.description` \{#agrag-common-data_models-graph_schema-RelationType-description}

```python
description: str
```

###### `agrag.common.data_models.graph_schema.RelationType.label` \{#agrag-common-data_models-graph_schema-RelationType-label}

```python
label: str
```

###### `agrag.common.data_models.graph_schema.RelationType.patterns` \{#agrag-common-data_models-graph_schema-RelationType-patterns}

```python
patterns: list[tuple[str, str]]
```

#### `agrag.common.data_models.normalization` \{#agrag-common-data_models-normalization}

The Normalization model: how a loader turned source bytes into text.

**Classes:**

- [**Normalization**](#agrag-common-data_models-normalization-Normalization) – How a loader turned source bytes into `Document.text`.

##### `agrag.common.data_models.normalization.Normalization` \{#agrag-common-data_models-normalization-Normalization}

Bases: <code>BaseModel</code>

How a loader turned source bytes into `Document.text`.

Provenance offsets index the normalized text. A caller who needs offsets into
the raw source chooses `Normalization(bom="keep", newline="keep", unicode_form="none")`.

**Attributes:**

- [**bom**](#agrag-common-data_models-normalization-Normalization-bom) (<code>Literal['strip', 'keep']</code>) – `"strip"` removes a leading byte-order mark. `"keep"` leaves it.
- [**newline**](#agrag-common-data_models-normalization-Normalization-newline) (<code>Literal['lf', 'keep']</code>) – `"lf"` turns CRLF and CR into LF. `"keep"` leaves them.
- [**unicode_form**](#agrag-common-data_models-normalization-Normalization-unicode_form) (<code>Literal['NFKC', 'NFC', 'NFD', 'NFKD', 'none']</code>) – The Unicode normalization form to apply, or `"none"`.

###### `agrag.common.data_models.normalization.Normalization.bom` \{#agrag-common-data_models-normalization-Normalization-bom}

```python
bom: Literal['strip', 'keep'] = 'strip'
```

###### `agrag.common.data_models.normalization.Normalization.model_config` \{#agrag-common-data_models-normalization-Normalization-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

###### `agrag.common.data_models.normalization.Normalization.newline` \{#agrag-common-data_models-normalization-Normalization-newline}

```python
newline: Literal['lf', 'keep'] = 'lf'
```

###### `agrag.common.data_models.normalization.Normalization.unicode_form` \{#agrag-common-data_models-normalization-Normalization-unicode_form}

```python
unicode_form: Literal['NFKC', 'NFC', 'NFD', 'NFKD', 'none'] = 'NFKC'
```

#### `agrag.common.data_models.provenance` \{#agrag-common-data_models-provenance}

Provenance types for a chunk.

A chunk's provenance shows where its text came from in the source. The shape of the
provenance depends on which chunker made the chunk.

**Classes:**

- [**BoundingBox**](#agrag-common-data_models-provenance-BoundingBox) – A box on a page, in page coordinates.
- [**PageProvenance**](#agrag-common-data_models-provenance-PageProvenance) – The location of a chunk across one or more pages.
- [**PageSpan**](#agrag-common-data_models-provenance-PageSpan) – One page's part of a chunk.
- [**TextProvenance**](#agrag-common-data_models-provenance-TextProvenance) – The location of a chunk inside flattened document text.

##### `agrag.common.data_models.provenance.BoundingBox` \{#agrag-common-data_models-provenance-BoundingBox}

Bases: <code>BaseModel</code>

A box on a page, in page coordinates.

**Attributes:**

- [**x0**](#agrag-common-data_models-provenance-BoundingBox-x0) (<code>float</code>) – The left edge.
- [**y0**](#agrag-common-data_models-provenance-BoundingBox-y0) (<code>float</code>) – The top edge.
- [**x1**](#agrag-common-data_models-provenance-BoundingBox-x1) (<code>float</code>) – The right edge.
- [**y1**](#agrag-common-data_models-provenance-BoundingBox-y1) (<code>float</code>) – The bottom edge.

###### `agrag.common.data_models.provenance.BoundingBox.x0` \{#agrag-common-data_models-provenance-BoundingBox-x0}

```python
x0: float
```

###### `agrag.common.data_models.provenance.BoundingBox.x1` \{#agrag-common-data_models-provenance-BoundingBox-x1}

```python
x1: float
```

###### `agrag.common.data_models.provenance.BoundingBox.y0` \{#agrag-common-data_models-provenance-BoundingBox-y0}

```python
y0: float
```

###### `agrag.common.data_models.provenance.BoundingBox.y1` \{#agrag-common-data_models-provenance-BoundingBox-y1}

```python
y1: float
```

##### `agrag.common.data_models.provenance.PageProvenance` \{#agrag-common-data_models-provenance-PageProvenance}

Bases: <code>BaseModel</code>

The location of a chunk across one or more pages.

A chunk can start on one page and end on the next page. Each entry in `page_spans`
covers one page.

**Attributes:**

- [**kind**](#agrag-common-data_models-provenance-PageProvenance-kind) (<code>Literal['page']</code>) – The literal tag `"page"`. Marks this as page provenance.
- [**page_spans**](#agrag-common-data_models-provenance-PageProvenance-page_spans) (<code>list\[[PageSpan](#agrag-common-data_models-provenance-PageSpan)\]</code>) – The page spans for this chunk. Has more than one entry when
  the chunk crosses a page boundary.

###### `agrag.common.data_models.provenance.PageProvenance.kind` \{#agrag-common-data_models-provenance-PageProvenance-kind}

```python
kind: Literal['page'] = 'page'
```

###### `agrag.common.data_models.provenance.PageProvenance.page_spans` \{#agrag-common-data_models-provenance-PageProvenance-page_spans}

```python
page_spans: list[PageSpan]
```

##### `agrag.common.data_models.provenance.PageSpan` \{#agrag-common-data_models-provenance-PageSpan}

Bases: <code>BaseModel</code>

One page's part of a chunk.

**Attributes:**

- [**page_no**](#agrag-common-data_models-provenance-PageSpan-page_no) (<code>int</code>) – The page number.
- [**bbox**](#agrag-common-data_models-provenance-PageSpan-bbox) (<code>[BoundingBox](#agrag-common-data_models-provenance-BoundingBox)</code>) – The box on the page that holds this part of the chunk.

###### `agrag.common.data_models.provenance.PageSpan.bbox` \{#agrag-common-data_models-provenance-PageSpan-bbox}

```python
bbox: BoundingBox
```

###### `agrag.common.data_models.provenance.PageSpan.page_no` \{#agrag-common-data_models-provenance-PageSpan-page_no}

```python
page_no: int
```

##### `agrag.common.data_models.provenance.TextProvenance` \{#agrag-common-data_models-provenance-TextProvenance}

Bases: <code>BaseModel</code>

The location of a chunk inside flattened document text.

The offsets index the normalized text in `Document.text`, not the raw source.
See `Normalization`.

**Attributes:**

- [**kind**](#agrag-common-data_models-provenance-TextProvenance-kind) (<code>Literal['text']</code>) – The literal tag `"text"`. Marks this as text provenance.
- [**char_start**](#agrag-common-data_models-provenance-TextProvenance-char_start) (<code>int</code>) – The start character offset in the document text.
- [**char_end**](#agrag-common-data_models-provenance-TextProvenance-char_end) (<code>int</code>) – The end character offset in the document text.
- [**line_start**](#agrag-common-data_models-provenance-TextProvenance-line_start) (<code>int | None</code>) – The start line number. Empty when the loader does not track lines.
- [**line_end**](#agrag-common-data_models-provenance-TextProvenance-line_end) (<code>int | None</code>) – The end line number. Empty when the loader does not track lines.

###### `agrag.common.data_models.provenance.TextProvenance.char_end` \{#agrag-common-data_models-provenance-TextProvenance-char_end}

```python
char_end: int
```

###### `agrag.common.data_models.provenance.TextProvenance.char_start` \{#agrag-common-data_models-provenance-TextProvenance-char_start}

```python
char_start: int
```

###### `agrag.common.data_models.provenance.TextProvenance.kind` \{#agrag-common-data_models-provenance-TextProvenance-kind}

```python
kind: Literal['text'] = 'text'
```

###### `agrag.common.data_models.provenance.TextProvenance.line_end` \{#agrag-common-data_models-provenance-TextProvenance-line_end}

```python
line_end: int | None = None
```

###### `agrag.common.data_models.provenance.TextProvenance.line_start` \{#agrag-common-data_models-provenance-TextProvenance-line_start}

```python
line_start: int | None = None
```

#### `agrag.common.data_models.query_value` \{#agrag-common-data_models-query_value}

A result row returned by a direct graph query.

**Classes:**

- [**QueryValue**](#agrag-common-data_models-query_value-QueryValue) – One result row returned by a generated graph query.

##### `agrag.common.data_models.query_value.QueryValue` \{#agrag-common-data_models-query_value-QueryValue}

Bases: <code>BaseModel</code>

One result row returned by a generated graph query.

**Attributes:**

- [**id**](#agrag-common-data_models-query_value-QueryValue-id) (<code>UUID</code>) –
- [**value**](#agrag-common-data_models-query_value-QueryValue-value) (<code>Any</code>) –

###### `agrag.common.data_models.query_value.QueryValue.id` \{#agrag-common-data_models-query_value-QueryValue-id}

```python
id: UUID = Field(default_factory=uuid4)
```

###### `agrag.common.data_models.query_value.QueryValue.value` \{#agrag-common-data_models-query_value-QueryValue-value}

```python
value: Any
```

#### `agrag.common.data_models.relation` \{#agrag-common-data_models-relation}

The canonical, deduped graph relationship that merge mechanics produces.

**Classes:**

- [**Relation**](#agrag-common-data_models-relation-Relation) – A resolved relationship between two Entity nodes.

##### `agrag.common.data_models.relation.Relation` \{#agrag-common-data_models-relation-Relation}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A resolved relationship between two Entity nodes.

**Attributes:**

- [**type**](#agrag-common-data_models-relation-Relation-type) (<code>str</code>) – The RelationType label this relationship was resolved as.
- [**source_id**](#agrag-common-data_models-relation-Relation-source_id) (<code>UUID</code>) – The id of the source Entity.
- [**target_id**](#agrag-common-data_models-relation-Relation-target_id) (<code>UUID</code>) – The id of the target Entity.
- [**properties**](#agrag-common-data_models-relation-Relation-properties) (<code>dict\[str, object\]</code>) – Field-resolved property values.
- [**source_chunk_ids**](#agrag-common-data_models-relation-Relation-source_chunk_ids) (<code>list\[UUID\]</code>) – Ids of every Chunk a mention contributing to this
  relationship came from. A relationship attested by more than one
  source has more than one id here, rather than existing as
  parallel edges.

**Functions:**

- [**to_relation_record**](#agrag-common-data_models-relation-Relation-to_relation_record) – Return this relationship as a GraphStore write record.

###### `agrag.common.data_models.relation.Relation.created_at` \{#agrag-common-data_models-relation-Relation-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.relation.Relation.id` \{#agrag-common-data_models-relation-Relation-id}

```python
id: UUID
```

###### `agrag.common.data_models.relation.Relation.metadata` \{#agrag-common-data_models-relation-Relation-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.relation.Relation.properties` \{#agrag-common-data_models-relation-Relation-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

###### `agrag.common.data_models.relation.Relation.source_chunk_ids` \{#agrag-common-data_models-relation-Relation-source_chunk_ids}

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

###### `agrag.common.data_models.relation.Relation.source_id` \{#agrag-common-data_models-relation-Relation-source_id}

```python
source_id: UUID
```

###### `agrag.common.data_models.relation.Relation.target_id` \{#agrag-common-data_models-relation-Relation-target_id}

```python
target_id: UUID
```

###### `agrag.common.data_models.relation.Relation.to_relation_record` \{#agrag-common-data_models-relation-Relation-to_relation_record}

```python
to_relation_record() -> RelationRecord
```

Return this relationship as a GraphStore write record.

###### `agrag.common.data_models.relation.Relation.type` \{#agrag-common-data_models-relation-Relation-type}

```python
type: str
```

#### `agrag.common.data_models.resolved_entity` \{#agrag-common-data_models-resolved_entity}

Materialized identity clusters for non-destructive entity resolution.

**Classes:**

- [**ResolvedEntity**](#agrag-common-data_models-resolved_entity-ResolvedEntity) – A materialized cluster of entities that refer to the same thing.

**Attributes:**

- [**MATCHES_RELATION**](#agrag-common-data_models-resolved_entity-MATCHES_RELATION) –
- [**RESOLVED_AS_RELATION**](#agrag-common-data_models-resolved_entity-RESOLVED_AS_RELATION) –
- [**RESOLVED_ENTITY_LABEL**](#agrag-common-data_models-resolved_entity-RESOLVED_ENTITY_LABEL) –

##### `agrag.common.data_models.resolved_entity.MATCHES_RELATION` \{#agrag-common-data_models-resolved_entity-MATCHES_RELATION}

```python
MATCHES_RELATION = 'MATCHES'
```

##### `agrag.common.data_models.resolved_entity.RESOLVED_AS_RELATION` \{#agrag-common-data_models-resolved_entity-RESOLVED_AS_RELATION}

```python
RESOLVED_AS_RELATION = 'RESOLVED_AS'
```

##### `agrag.common.data_models.resolved_entity.RESOLVED_ENTITY_LABEL` \{#agrag-common-data_models-resolved_entity-RESOLVED_ENTITY_LABEL}

```python
RESOLVED_ENTITY_LABEL = 'ResolvedEntity'
```

##### `agrag.common.data_models.resolved_entity.ResolvedEntity` \{#agrag-common-data_models-resolved_entity-ResolvedEntity}

Bases: <code>[DataPoint](#agrag-common-data_models-data_point-DataPoint)</code>

A materialized cluster of entities that refer to the same thing.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-resolved_entity-ResolvedEntity-to_node_record) – Return this resolved entity as a graph write record.

**Attributes:**

- [**created_at**](#agrag-common-data_models-resolved_entity-ResolvedEntity-created_at) (<code>datetime</code>) –
- [**embedding**](#agrag-common-data_models-resolved_entity-ResolvedEntity-embedding) (<code>list\[float\] | None</code>) –
- [**embedding_text**](#agrag-common-data_models-resolved_entity-ResolvedEntity-embedding_text) (<code>str</code>) – Return the text used to embed this resolved entity.
- [**id**](#agrag-common-data_models-resolved_entity-ResolvedEntity-id) (<code>UUID</code>) –
- [**label**](#agrag-common-data_models-resolved_entity-ResolvedEntity-label) (<code>str</code>) –
- [**member_ids**](#agrag-common-data_models-resolved_entity-ResolvedEntity-member_ids) (<code>list\[UUID\]</code>) –
- [**metadata**](#agrag-common-data_models-resolved_entity-ResolvedEntity-metadata) (<code>dict\[str, Any\]</code>) –
- [**name**](#agrag-common-data_models-resolved_entity-ResolvedEntity-name) (<code>str</code>) –
- [**properties**](#agrag-common-data_models-resolved_entity-ResolvedEntity-properties) (<code>dict\[str, object\]</code>) –
- [**vector_sync_error**](#agrag-common-data_models-resolved_entity-ResolvedEntity-vector_sync_error) (<code>str | None</code>) –
- [**vector_sync_status**](#agrag-common-data_models-resolved_entity-ResolvedEntity-vector_sync_status) (<code>Literal['pending', 'synced', 'failed']</code>) –

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.created_at` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.embedding` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-embedding}

```python
embedding: list[float] | None = None
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.embedding_text` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-embedding_text}

```python
embedding_text: str
```

Return the text used to embed this resolved entity.

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.id` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-id}

```python
id: UUID
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.label` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-label}

```python
label: str
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.member_ids` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-member_ids}

```python
member_ids: list[UUID] = Field(default_factory=list)
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.metadata` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.name` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-name}

```python
name: str
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.properties` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-properties}

```python
properties: dict[str, object] = Field(default_factory=dict)
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.to_node_record` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this resolved entity as a graph write record.

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.vector_sync_error` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-vector_sync_error}

```python
vector_sync_error: str | None = None
```

###### `agrag.common.data_models.resolved_entity.ResolvedEntity.vector_sync_status` \{#agrag-common-data_models-resolved_entity-ResolvedEntity-vector_sync_status}

```python
vector_sync_status: Literal['pending', 'synced', 'failed'] = 'pending'
```

#### `agrag.common.data_models.search_result` \{#agrag-common-data_models-search_result}

One retrieved item, tagged with source and relevance score.

**Classes:**

- [**SearchResult**](#agrag-common-data_models-search_result-SearchResult) – One retrieved item, tagged with where it came from.

##### `agrag.common.data_models.search_result.SearchResult` \{#agrag-common-data_models-search_result-SearchResult}

Bases: <code>BaseModel</code>

One retrieved item, tagged with where it came from.

**Attributes:**

- [**item**](#agrag-common-data_models-search_result-SearchResult-item) (<code>Union\[[Entity](#agrag-common-data_models-entity-Entity), [ResolvedEntity](#agrag-common-data_models-resolved_entity-ResolvedEntity), [Relation](#agrag-common-data_models-relation-Relation), [Chunk](#agrag-common-data_models-chunk-Chunk), [Community](#agrag-common-data_models-community-Community), [QueryValue](#agrag-common-data_models-query_value-QueryValue)\]</code>) – The retrieved Entity, ResolvedEntity, Relation, Chunk, or
  Community, or scalar query value.
- [**score**](#agrag-common-data_models-search_result-SearchResult-score) (<code>float</code>) – The method's own relevance score. Not comparable
  across methods until Fusion normalizes it.
- [**method**](#agrag-common-data_models-search_result-SearchResult-method) (<code>str</code>) – The name of the retrieval method that produced
  this result.
- [**parent**](#agrag-common-data_models-search_result-SearchResult-parent) (<code>[Chunk](#agrag-common-data_models-chunk-Chunk) | None</code>) – The parent chunk of a child chunk result, so a caller can show the
  larger passage. `None` for every other result.

###### `agrag.common.data_models.search_result.SearchResult.identity_key` \{#agrag-common-data_models-search_result-SearchResult-identity_key}

```python
identity_key: tuple[str, UUID]
```

Return the (type, id) key Fusion deduplicates on.

**Raises:**

- <code>ValueError</code> – The item has no id, so it cannot be
  deduplicated.

###### `agrag.common.data_models.search_result.SearchResult.item` \{#agrag-common-data_models-search_result-SearchResult-item}

```python
item: Union[Entity, ResolvedEntity, Relation, Chunk, Community, QueryValue]
```

###### `agrag.common.data_models.search_result.SearchResult.method` \{#agrag-common-data_models-search_result-SearchResult-method}

```python
method: str
```

###### `agrag.common.data_models.search_result.SearchResult.parent` \{#agrag-common-data_models-search_result-SearchResult-parent}

```python
parent: Chunk | None = None
```

###### `agrag.common.data_models.search_result.SearchResult.score` \{#agrag-common-data_models-search_result-SearchResult-score}

```python
score: float
```

#### `agrag.common.data_models.stage_failure` \{#agrag-common-data_models-stage_failure}

Per-stage failure record and its per-call cap.

**Classes:**

- [**CappedFailures**](#agrag-common-data_models-stage_failure-CappedFailures) – A capped failure list plus the true count it was built from.
- [**StageFailure**](#agrag-common-data_models-stage_failure-StageFailure) – One item's failure within a pipeline stage.

**Functions:**

- [**cap_failures**](#agrag-common-data_models-stage_failure-cap_failures) – Return failures capped per stage, with the untruncated true count.

**Attributes:**

- [**MAX_FAILURES_PER_STAGE**](#agrag-common-data_models-stage_failure-MAX_FAILURES_PER_STAGE) –
- [**logger**](#agrag-common-data_models-stage_failure-logger) –

##### `agrag.common.data_models.stage_failure.CappedFailures` \{#agrag-common-data_models-stage_failure-CappedFailures}

Bases: <code>NamedTuple</code>

A capped failure list plus the true count it was built from.

**Attributes:**

- [**items**](#agrag-common-data_models-stage_failure-CappedFailures-items) (<code>list\[[StageFailure](#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – The failure records, truncated to the per-stage cap.
- [**total**](#agrag-common-data_models-stage_failure-CappedFailures-total) (<code>int</code>) – How many failures the stage actually recorded, before any
  truncation.
- [**truncated**](#agrag-common-data_models-stage_failure-CappedFailures-truncated) (<code>bool</code>) – Whether `items` was cut to the per-stage cap.

###### `agrag.common.data_models.stage_failure.CappedFailures.items` \{#agrag-common-data_models-stage_failure-CappedFailures-items}

```python
items: list[StageFailure]
```

###### `agrag.common.data_models.stage_failure.CappedFailures.total` \{#agrag-common-data_models-stage_failure-CappedFailures-total}

```python
total: int
```

###### `agrag.common.data_models.stage_failure.CappedFailures.truncated` \{#agrag-common-data_models-stage_failure-CappedFailures-truncated}

```python
truncated: bool
```

##### `agrag.common.data_models.stage_failure.MAX_FAILURES_PER_STAGE` \{#agrag-common-data_models-stage_failure-MAX_FAILURES_PER_STAGE}

```python
MAX_FAILURES_PER_STAGE = 200
```

##### `agrag.common.data_models.stage_failure.StageFailure` \{#agrag-common-data_models-stage_failure-StageFailure}

Bases: <code>BaseModel</code>

One item's failure within a pipeline stage.

**Attributes:**

- [**item_id**](#agrag-common-data_models-stage_failure-StageFailure-item_id) (<code>str</code>) – The chunk id, mention id, or batch id — whichever unit
  the stage failed on.
- [**error_type**](#agrag-common-data_models-stage_failure-StageFailure-error_type) (<code>str</code>) – The exception's class name.
- [**error_message**](#agrag-common-data_models-stage_failure-StageFailure-error_message) (<code>str</code>) – The exception's message.
- [**trace_id**](#agrag-common-data_models-stage_failure-StageFailure-trace_id) (<code>str | None</code>) – The OTel trace id correlating to the full span detail,
  when tracing is configured.
- [**span_id**](#agrag-common-data_models-stage_failure-StageFailure-span_id) (<code>str | None</code>) – The OTel span id within that trace.

###### `agrag.common.data_models.stage_failure.StageFailure.error_message` \{#agrag-common-data_models-stage_failure-StageFailure-error_message}

```python
error_message: str
```

###### `agrag.common.data_models.stage_failure.StageFailure.error_type` \{#agrag-common-data_models-stage_failure-StageFailure-error_type}

```python
error_type: str
```

###### `agrag.common.data_models.stage_failure.StageFailure.item_id` \{#agrag-common-data_models-stage_failure-StageFailure-item_id}

```python
item_id: str
```

###### `agrag.common.data_models.stage_failure.StageFailure.span_id` \{#agrag-common-data_models-stage_failure-StageFailure-span_id}

```python
span_id: str | None = None
```

###### `agrag.common.data_models.stage_failure.StageFailure.trace_id` \{#agrag-common-data_models-stage_failure-StageFailure-trace_id}

```python
trace_id: str | None = None
```

##### `agrag.common.data_models.stage_failure.cap_failures` \{#agrag-common-data_models-stage_failure-cap_failures}

```python
cap_failures(failures:list[StageFailure]) -> CappedFailures
```

Return failures capped per stage, with the untruncated true count.

Logs a warning when truncation occurs, since the capped list alone no
longer reflects how many items actually failed.

**Parameters:**

- **failures** (<code>list\[[StageFailure](#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Every failure the stage recorded.

**Returns:**

- <code>[CappedFailures](#agrag-common-data_models-stage_failure-CappedFailures)</code> – The capped list, the true failure count, and whether the list was
- <code>[CappedFailures](#agrag-common-data_models-stage_failure-CappedFailures)</code> – truncated.

##### `agrag.common.data_models.stage_failure.logger` \{#agrag-common-data_models-stage_failure-logger}

```python
logger = logging.getLogger(__name__)
```

#### `agrag.common.data_models.vector_record` \{#agrag-common-data_models-vector_record}

Vector storage record shapes shared by VectorStore and GraphStore.

**Classes:**

- [**Distance**](#agrag-common-data_models-vector_record-Distance) – A distance metric a vector index compares embeddings with.
- [**VectorHit**](#agrag-common-data_models-vector_record-VectorHit) – One search result: a matched id, its score, and its stored payload.
- [**VectorRecord**](#agrag-common-data_models-vector_record-VectorRecord) – One vector and its payload, ready to write to a collection or index.

**Attributes:**

- [**PENDING_VECTOR_FLAG**](#agrag-common-data_models-vector_record-PENDING_VECTOR_FLAG) – Payload flag marking a vector as written by an in-flight Cutover Job.

##### `agrag.common.data_models.vector_record.Distance` \{#agrag-common-data_models-vector_record-Distance}

Bases: <code>StrEnum</code>

A distance metric a vector index compares embeddings with.

**Attributes:**

- [**COSINE**](#agrag-common-data_models-vector_record-Distance-COSINE) – Cosine similarity. The default for most embedding models.
- [**EUCLID**](#agrag-common-data_models-vector_record-Distance-EUCLID) – Euclidean (L2) distance.
- [**DOT**](#agrag-common-data_models-vector_record-Distance-DOT) – Dot product.

###### `agrag.common.data_models.vector_record.Distance.COSINE` \{#agrag-common-data_models-vector_record-Distance-COSINE}

```python
COSINE = 'Cosine'
```

###### `agrag.common.data_models.vector_record.Distance.DOT` \{#agrag-common-data_models-vector_record-Distance-DOT}

```python
DOT = 'Dot'
```

###### `agrag.common.data_models.vector_record.Distance.EUCLID` \{#agrag-common-data_models-vector_record-Distance-EUCLID}

```python
EUCLID = 'Euclid'
```

##### `agrag.common.data_models.vector_record.PENDING_VECTOR_FLAG` \{#agrag-common-data_models-vector_record-PENDING_VECTOR_FLAG}

```python
PENDING_VECTOR_FLAG = '_pending'
```

Payload flag marking a vector as written by an in-flight Cutover Job.

Mirrored at write time and cleared at commit. Payload filters only match
on present values, so pending-exclusion needs this explicit boolean
rather than relying on the job-id key's absence.

Every backend's filter compiler reads the flag two ways: a filter that
omits it, or sets it `False`, excludes records flagged true while
still returning records written before the flag existed, and a filter
that sets it `True` returns only the flagged records, which is the
maintenance path that has to see a job's own in-flight vectors.

##### `agrag.common.data_models.vector_record.VectorHit` \{#agrag-common-data_models-vector_record-VectorHit}

Bases: <code>BaseModel</code>

One search result: a matched id, its score, and its stored payload.

Returned by both `VectorStore.search`/`hybrid_search` and
`GraphStore.vector_search`, so a caller cannot tell which store produced
a given hit.

**Attributes:**

- [**id**](#agrag-common-data_models-vector_record-VectorHit-id) (<code>UUID</code>) – The id of the matched record.
- [**score**](#agrag-common-data_models-vector_record-VectorHit-score) (<code>float</code>) – The match score. Higher means a closer match, regardless of
  which distance metric the collection uses.
- [**payload**](#agrag-common-data_models-vector_record-VectorHit-payload) (<code>dict\[str, Any\]</code>) – The payload stored with the matched record.

###### `agrag.common.data_models.vector_record.VectorHit.id` \{#agrag-common-data_models-vector_record-VectorHit-id}

```python
id: UUID
```

###### `agrag.common.data_models.vector_record.VectorHit.payload` \{#agrag-common-data_models-vector_record-VectorHit-payload}

```python
payload: dict[str, Any]
```

###### `agrag.common.data_models.vector_record.VectorHit.score` \{#agrag-common-data_models-vector_record-VectorHit-score}

```python
score: float
```

##### `agrag.common.data_models.vector_record.VectorRecord` \{#agrag-common-data_models-vector_record-VectorRecord}

Bases: <code>BaseModel</code>

One vector and its payload, ready to write to a collection or index.

The collection or index name is a call argument on the store, not a field
here, so one record type can target any collection.

**Attributes:**

- [**id**](#agrag-common-data_models-vector_record-VectorRecord-id) (<code>UUID</code>) – The record id. Callers set this to the id of the domain object the
  vector represents.
- [**vector**](#agrag-common-data_models-vector_record-VectorRecord-vector) (<code>list\[float\]</code>) – The dense embedding.
- [**payload**](#agrag-common-data_models-vector_record-VectorRecord-payload) (<code>dict\[str, Any\]</code>) – Fields stored alongside the vector, such as the source text or
  a chunk id. Read back unchanged by `search`/`hybrid_search`.

###### `agrag.common.data_models.vector_record.VectorRecord.id` \{#agrag-common-data_models-vector_record-VectorRecord-id}

```python
id: UUID
```

###### `agrag.common.data_models.vector_record.VectorRecord.payload` \{#agrag-common-data_models-vector_record-VectorRecord-payload}

```python
payload: dict[str, Any]
```

###### `agrag.common.data_models.vector_record.VectorRecord.vector` \{#agrag-common-data_models-vector_record-VectorRecord-vector}

```python
vector: list[float]
```

### `agrag.common.text` \{#agrag-common-text}

Shared text normalization used across resolution and merge-key computation.

**Functions:**

- [**normalize_text**](#agrag-common-text-normalize_text) – Return text stripped and case-folded for identity comparison.

#### `agrag.common.text.normalize_text` \{#agrag-common-text-normalize_text}

```python
normalize_text(text:str) -> str
```

Return text stripped and case-folded for identity comparison.

**Parameters:**

- **text** (<code>str</code>) – The text to normalize.

**Returns:**

- <code>str</code> – The stripped, case-folded text.

### `agrag.common.validation` \{#agrag-common-validation}

Validation helpers shared across storage backends.

**Functions:**

- [**require_encrypted_remote_connection**](#agrag-common-validation-require_encrypted_remote_connection) – Reject a plaintext connection to a non-local host carrying a credential.
- [**require_positive_batch_size**](#agrag-common-validation-require_positive_batch_size) – Check that a backend write's `batch_size` is usable.
- [**require_positive_max_concurrency**](#agrag-common-validation-require_positive_max_concurrency) – Check that a concurrency limit is positive.
- [**require_valid_alpha**](#agrag-common-validation-require_valid_alpha) – Check that a `hybrid_search` `alpha` is a valid dense/keyword weight.
- [**require_valid_search_limit**](#agrag-common-validation-require_valid_search_limit) – Check that a search/hybrid_search `limit` is usable across every backend.

**Attributes:**

- [**MAX_SEARCH_LIMIT**](#agrag-common-validation-MAX_SEARCH_LIMIT) –

#### `agrag.common.validation.MAX_SEARCH_LIMIT` \{#agrag-common-validation-MAX_SEARCH_LIMIT}

```python
MAX_SEARCH_LIMIT = 16384
```

#### `agrag.common.validation.require_encrypted_remote_connection` \{#agrag-common-validation-require_encrypted_remote_connection}

```python
require_encrypted_remote_connection(*, url:str, has_credential:bool, encrypted_schemes:Collection[str], require_encryption:bool = False) -> None
```

Reject a plaintext connection to a non-local host carrying a credential.

A scheme outside `encrypted_schemes` sends everything on the
connection, including any configured credential, unencrypted. That is
the normal, safe shape of local development against a Docker Compose
service on localhost, but the same plaintext default pointed at a real
remote host would leak credentials and data to network interception.
Loopback hosts are always allowed, regardless of scheme or credential.

Without `require_encryption`, a connection carrying no credential is
always allowed: many production deployments run an unauthenticated
backend on a private network (a VPC, a cluster-internal service) and
rely on network segmentation rather than transport encryption, and this
check cannot distinguish that from a public host from the URL alone.
`require_encryption` opts a deployment out of that default, for a
stricter posture where every non-local connection must be encrypted
regardless of credential.

**Parameters:**

- **url** (<code>str</code>) – The connection URL or URI to check.
- **has_credential** (<code>bool</code>) – Whether a credential (API key, token, password) is
  configured for this connection.
- **encrypted_schemes** (<code>Collection\[str\]</code>) – The URL schemes considered encrypted for this
  backend, for example `{"https"}` or `{"bolt+s", "neo4j+s"}`.
- **require_encryption** (<code>bool</code>) – When `True`, reject plaintext to a non-local
  host even without a configured credential.

**Raises:**

- <code>ValueError</code> – `url` uses a scheme outside `encrypted_schemes`, its
  host is not loopback, and either `has_credential` or
  `require_encryption` is `True`.

#### `agrag.common.validation.require_positive_batch_size` \{#agrag-common-validation-require_positive_batch_size}

```python
require_positive_batch_size(batch_size:int) -> None
```

Check that a backend write's `batch_size` is usable.

Every backend chunks writes with `range(0, len(records), batch_size)`.
A non-positive value breaks that: zero raises `ValueError` from
`range` itself, and a negative value silently produces an empty range,
skipping every record without error.

**Parameters:**

- **batch_size** (<code>int</code>) – The batch size to check.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

#### `agrag.common.validation.require_positive_max_concurrency` \{#agrag-common-validation-require_positive_max_concurrency}

```python
require_positive_max_concurrency(max_concurrency:int) -> None
```

Check that a concurrency limit is positive.

#### `agrag.common.validation.require_valid_alpha` \{#agrag-common-validation-require_valid_alpha}

```python
require_valid_alpha(alpha:float) -> None
```

Check that a `hybrid_search` `alpha` is a valid dense/keyword weight.

`alpha` is only meaningful in `[0.0, 1.0]`: `1.0` is pure dense,
`0.0` is pure keyword. Outside that range, backends behave
differently: Qdrant's client-side blend still produces a
mathematically well-defined but meaningless score, while a backend's
native ranker may reject the value outright.

**Parameters:**

- **alpha** (<code>float</code>) – The dense/keyword balance to check.

**Raises:**

- <code>ValueError</code> – `alpha` is outside `[0.0, 1.0]`.

#### `agrag.common.validation.require_valid_search_limit` \{#agrag-common-validation-require_valid_search_limit}

```python
require_valid_search_limit(limit:int) -> None
```

Check that a search/hybrid_search `limit` is usable across every backend.

Backends fail differently outside this range: Milvus raises for a
non-positive `limit` or one above `MAX_SEARCH_LIMIT` (its own
query/search result-window ceiling), while Qdrant and Weaviate may
instead return an empty or silently truncated result. Enforcing the
tightest bound uniformly means a given `limit` either works, or fails
the same way, regardless of which backend is configured.

**Parameters:**

- **limit** (<code>int</code>) – The requested maximum number of hits.

**Raises:**

- <code>ValueError</code> – `limit` is not a positive integer, or exceeds
  `MAX_SEARCH_LIMIT`.
