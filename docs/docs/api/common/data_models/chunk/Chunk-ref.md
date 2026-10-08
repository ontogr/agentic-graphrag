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
- [**provenance**](#agrag-common-data_models-chunk-Chunk-provenance) (<code>[TextProvenance](../provenance/TextProvenance.md) | [PageProvenance](../provenance/PageProvenance.md)</code>) – The location of this chunk in its source. A text source gives
  character offsets. A source with page layout gives pages and boxes, and
  a source with neither gives no page spans.
- [**heading_path**](#agrag-common-data_models-chunk-Chunk-heading_path) (<code>list\[str\]</code>) – The headings that contain this chunk, from outermost to
  innermost. Empty for a chunk with no heading above it.
- [**content_kind**](#agrag-common-data_models-chunk-Chunk-content_kind) (<code>Literal['text', 'table']</code>) – `"text"` for a chunk of running text and `"table"` for a
  chunk made from a table.
- [**chunker**](#agrag-common-data_models-chunk-Chunk-chunker) (<code>str | None</code>) – The name of the chunker that made this chunk. `None` for a chunk
  written before chunkers were recorded.
- [**chunker_hash**](#agrag-common-data_models-chunk-Chunk-chunker_hash) (<code>str | None</code>) – The fingerprint of the settings of the chunker that made this
  chunk. `None` for a chunk written before chunkers were recorded.
- [**section_ids**](#agrag-common-data_models-chunk-Chunk-section_ids) (<code>list\[UUID\]</code>) – The node ids of the sections whose text the chunk holds, in
  reading order. Empty for a document with no sections.
- [**position**](#agrag-common-data_models-chunk-Chunk-position) (<code>int</code>) – The reading-order number of the first unit in the chunk. The
  ingestion code uses it to order the children of a section. The graph
  does not store it.

**Functions:**

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
content_kind: Literal['text', 'table'] = 'text'
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

## `index` \{#agrag-common-data_models-chunk-Chunk-index}

```python
index: int = 0
```

## `metadata` \{#agrag-common-data_models-chunk-Chunk-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `position` \{#agrag-common-data_models-chunk-Chunk-position}

```python
position: int = Field(default=0, exclude=True)
```

## `provenance` \{#agrag-common-data_models-chunk-Chunk-provenance}

```python
provenance: TextProvenance | PageProvenance = Field(discriminator='kind')
```

## `section_ids` \{#agrag-common-data_models-chunk-Chunk-section_ids}

```python
section_ids: list[UUID] = Field(default_factory=list)
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
