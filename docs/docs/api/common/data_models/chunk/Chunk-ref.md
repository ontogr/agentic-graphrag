---
title: agrag.common.data_models.chunk.Chunk
sidebar_label: Chunk
---

# `agrag.common.data_models.chunk.Chunk` \{#agrag-common-data_models-chunk-Chunk}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

One retrieval-sized piece of a Document.

**Attributes:**

- [**document_id**](#agrag-common-data_models-chunk-Chunk-document_id) (<code>UUID</code>) – The id of the persisted Document graph node this chunk
  belongs to (see `Document.node_id_for`). It stays stable across
  content versions of the same logical document. Per-version
  identity lives in `Chunk.id` instead.
- [**index**](#agrag-common-data_models-chunk-Chunk-index) (<code>int</code>) – The position of the chunk within its document, from 0.
- [**text**](#agrag-common-data_models-chunk-Chunk-text) (<code>str</code>) – The chunk text.
- [**provenance**](#agrag-common-data_models-chunk-Chunk-provenance) (<code>[TextProvenance](../provenance/TextProvenance.md) | [PageProvenance](../provenance/PageProvenance.md)</code>) – The location of this chunk in its source. The shape of this
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

## `chunker` \{#agrag-common-data_models-chunk-Chunk-chunker}

```python
chunker: str | None = None
```

## `chunker_hash` \{#agrag-common-data_models-chunk-Chunk-chunker_hash}

```python
chunker_hash: str | None = None
```

## `content_kind` \{#agrag-common-data_models-chunk-Chunk-content_kind}

```python
content_kind: Literal['text', 'table_row', 'code', 'heading'] = 'text'
```

## `contextual_text` \{#agrag-common-data_models-chunk-Chunk-contextual_text}

```python
contextual_text: str
```

The text with its heading path above it, for embedding.

The stored text and its offsets do not change. A chunk with no heading path
returns its text.

## `created_at` \{#agrag-common-data_models-chunk-Chunk-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `document_id` \{#agrag-common-data_models-chunk-Chunk-document_id}

```python
document_id: UUID
```

## `embedding` \{#agrag-common-data_models-chunk-Chunk-embedding}

```python
embedding: list[float] | None = None
```

## `heading_path` \{#agrag-common-data_models-chunk-Chunk-heading_path}

```python
heading_path: list[str] = Field(default_factory=list)
```

## `id` \{#agrag-common-data_models-chunk-Chunk-id}

```python
id: UUID | None = None
```

## `id_for` \{#agrag-common-data_models-chunk-Chunk-id_for}

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
- **provenance** (<code>[TextProvenance](../provenance/TextProvenance.md) | [PageProvenance](../provenance/PageProvenance.md)</code>) – The provenance of the chunk. Its type picks which id rule
  applies.
- **index** (<code>int</code>) – The position of the chunk within its document.
- **chunker_hash** (<code>str | None</code>) – The fingerprint of the chunker. Only a docling chunk
  uses it. A text chunk id ignores it.
- **level** (<code>int</code>) – The chunk level. A parent chunk (level 1) adds a level part, so a
  parent and a child with the same span get different ids. The id of a
  level 0 chunk does not change.

**Returns:**

- <code>UUID</code> – The chunk id.

## `index` \{#agrag-common-data_models-chunk-Chunk-index}

```python
index: int = 0
```

## `level` \{#agrag-common-data_models-chunk-Chunk-level}

```python
level: int = 0
```

## `metadata` \{#agrag-common-data_models-chunk-Chunk-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `parent_id` \{#agrag-common-data_models-chunk-Chunk-parent_id}

```python
parent_id: UUID | None = None
```

## `provenance` \{#agrag-common-data_models-chunk-Chunk-provenance}

```python
provenance: TextProvenance | PageProvenance = Field(discriminator='kind')
```

## `section_label` \{#agrag-common-data_models-chunk-Chunk-section_label}

```python
section_label() -> str | None
```

Return the heading path as one line, or `None` when the path is empty.

Whitespace runs in a heading become one space, and runs of three or more
dashes become one dash, so a heading cannot end the text block of the
extraction prompt.

## `text` \{#agrag-common-data_models-chunk-Chunk-text}

```python
text: str
```

## `to_node_record` \{#agrag-common-data_models-chunk-Chunk-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this chunk as a GraphStore write record.

Provenance is flattened to a plain JSON-safe dict via model_dump.
GraphStore's own serialize.node_params only converts UUIDs and walks
containers.

**Raises:**

- <code>ValueError</code> – id is None.
