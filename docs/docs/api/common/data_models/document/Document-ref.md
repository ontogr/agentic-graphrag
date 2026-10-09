---
title: agrag.common.data_models.document.Document
sidebar_label: Document
---

# `agrag.common.data_models.document.Document` \{#agrag-common-data_models-document-Document}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

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

- [**text**](#agrag-common-data_models-document-Document-text) (<code>str</code>) – The document text. For a docling source, this holds the docling
  Markdown export. The chunker does not read it for a docling source: the
  chunks come from `sections`.
- [**title**](#agrag-common-data_models-document-Document-title) (<code>str</code>) – The document title.
- [**uri**](#agrag-common-data_models-document-Document-uri) (<code>str</code>) – The location of the source. This value is not part of the document id.
- [**source_format**](#agrag-common-data_models-document-Document-source_format) (<code>[SourceFormat](SourceFormat.md)</code>) – The format the loader used to read this document.
- [**family**](#agrag-common-data_models-document-Document-family) (<code>[DocumentFamily](DocumentFamily.md)</code>) – The shape of the source: one document per file, or one document per
  record.
- [**content_hash**](#agrag-common-data_models-document-Document-content_hash) (<code>str</code>) – The hash that forms the document id.
- [**loader_name**](#agrag-common-data_models-document-Document-loader_name) (<code>str</code>) – The name of the loader that produced this document, for example
  `"text"` or `"docling"`.
- [**loader_version**](#agrag-common-data_models-document-Document-loader_version) (<code>str | None</code>) – The version of the loader package. Does not affect the
  document id.
- [**encoding**](#agrag-common-data_models-document-Document-encoding) (<code>str | None</code>) – The text encoding. Text loaders set this field. Other loaders
  leave it empty.
- [**source_hash**](#agrag-common-data_models-document-Document-source_hash) (<code>str | None</code>) – The hash of the whole source file. Record-family documents set
  this field.
- [**char_count**](#agrag-common-data_models-document-Document-char_count) (<code>int</code>) – The number of characters in `text`.
- [**line_count**](#agrag-common-data_models-document-Document-line_count) (<code>int | None</code>) – The number of lines in `text`. Some loaders do not set this field.
- [**record_index**](#agrag-common-data_models-document-Document-record_index) (<code>int | None</code>) – The 0-based row number in the source. Record-family documents
  set this field.
- [**record_id**](#agrag-common-data_models-document-Document-record_id) (<code>str | None</code>) – The value from the configured id column. Record-family documents
  set this field only when the caller configures an id column.
- [**raw_record**](#agrag-common-data_models-document-Document-raw_record) (<code>dict\[str, JsonValue\] | None</code>) – The original record data. A loader sets this field only when the
  caller asks for it.
- [**sections**](#agrag-common-data_models-document-Document-sections) (<code>list\[[DocumentSection](DocumentSection.md)\]</code>) – The headings of the document and the content under them, in reading
  order. A non-blank document with no headings has one section with an
  empty heading. A record row has none: its text is one unit of content.
  A document read without its text (`store_text` off) has none either.
- [**document_key**](#agrag-common-data_models-document-Document-document_key) (<code>str | None</code>) – The stable identifier for this document's persisted graph node.
  Independent of `id`, which changes with every content edit. Defaults to
  `uri` when not supplied.
- [**normalization**](#agrag-common-data_models-document-Document-normalization) (<code>[Normalization](../normalization/Normalization-ref.md) | None</code>) – How the loader normalized `text`. `None` for a document
  that no text loader made, such as a docling document or one built by hand.

**Functions:**

- [**id_for**](#agrag-common-data_models-document-Document-id_for) – Compute the document id.
- [**node_id_for**](#agrag-common-data_models-document-Document-node_id_for) – Compute the persisted Document graph node id.
- [**to_node_record**](#agrag-common-data_models-document-Document-to_node_record) – Return this document as a GraphStore write record for its graph node.

## `char_count` \{#agrag-common-data_models-document-Document-char_count}

```python
char_count: int
```

## `content_hash` \{#agrag-common-data_models-document-Document-content_hash}

```python
content_hash: str
```

## `created_at` \{#agrag-common-data_models-document-Document-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `document_key` \{#agrag-common-data_models-document-Document-document_key}

```python
document_key: str | None = None
```

## `encoding` \{#agrag-common-data_models-document-Document-encoding}

```python
encoding: str | None = None
```

## `family` \{#agrag-common-data_models-document-Document-family}

```python
family: DocumentFamily
```

## `id` \{#agrag-common-data_models-document-Document-id}

```python
id: UUID | None = None
```

## `id_for` \{#agrag-common-data_models-document-Document-id_for}

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

## `line_count` \{#agrag-common-data_models-document-Document-line_count}

```python
line_count: int | None = None
```

## `loader_name` \{#agrag-common-data_models-document-Document-loader_name}

```python
loader_name: str
```

## `loader_version` \{#agrag-common-data_models-document-Document-loader_version}

```python
loader_version: str | None = None
```

## `metadata` \{#agrag-common-data_models-document-Document-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `node_id_for` \{#agrag-common-data_models-document-Document-node_id_for}

```python
node_id_for(*, document_key:str) -> UUID
```

Compute the persisted Document graph node id.

Distinct from `id_for()`. This id is keyed on `document_key`, not
the content hash, so it stays the same across content changes to the
same logical document. Conflating the two ids gives every content
version of a document its own graph node instead of one node with a
changing content hash.

**Parameters:**

- **document_key** (<code>str</code>) – The document's stable key.

**Returns:**

- <code>UUID</code> – The Document graph node id.

## `normalization` \{#agrag-common-data_models-document-Document-normalization}

```python
normalization: Normalization | None = None
```

## `raw_record` \{#agrag-common-data_models-document-Document-raw_record}

```python
raw_record: dict[str, JsonValue] | None = None
```

## `record_id` \{#agrag-common-data_models-document-Document-record_id}

```python
record_id: str | None = None
```

## `record_index` \{#agrag-common-data_models-document-Document-record_index}

```python
record_index: int | None = None
```

## `resolved_document_key` \{#agrag-common-data_models-document-Document-resolved_document_key}

```python
resolved_document_key: str
```

Return the document key. It is never `None` after construction succeeds.

`document_key` is typed as optional because callers can omit it and
let `_resolve_document_key` default it to `uri`. Every constructed
`Document` has a non-`None` document key by the time callers see
it. Use this property instead of `document_key` where a non-optional
value is required, such as computing the persisted Document node id.

**Raises:**

- <code>RuntimeError</code> – `document_key` is still `None`, which means a validator
  was bypassed, for example via `model_construct`.

## `resolved_id` \{#agrag-common-data_models-document-Document-resolved_id}

```python
resolved_id: UUID
```

Return the document id. It is never `None` after construction succeeds.

`id` is typed as optional because callers can omit it and let
`_resolve_id` derive it. Every constructed `Document` has a
non-`None` id by the time callers see it. Use this property instead
of `id` where a non-optional value is required, such as building a
`Chunk`.

**Raises:**

- <code>RuntimeError</code> – `id` is still `None`, which means a validator was
  bypassed, for example via `model_construct`.

## `sections` \{#agrag-common-data_models-document-Document-sections}

```python
sections: list[DocumentSection] = Field(default_factory=list)
```

## `source_format` \{#agrag-common-data_models-document-Document-source_format}

```python
source_format: SourceFormat
```

## `source_hash` \{#agrag-common-data_models-document-Document-source_hash}

```python
source_hash: str | None = None
```

## `text` \{#agrag-common-data_models-document-Document-text}

```python
text: str
```

## `title` \{#agrag-common-data_models-document-Document-title}

```python
title: str
```

## `to_node_record` \{#agrag-common-data_models-document-Document-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this document as a GraphStore write record for its graph node.

The record excludes `text`: the persisted node exists for traversal and
the update no-op check, not to duplicate the document body already held
per-chunk.

## `uri` \{#agrag-common-data_models-document-Document-uri}

```python
uri: str
```
