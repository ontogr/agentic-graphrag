---
title: agrag.common.data_models.document.Document
sidebar_label: Document
---

# `agrag.common.data_models.document.Document` \{#agrag-common-data_models-document-Document}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

One unit of source text, before chunking.

A prose source, such as a Markdown file, makes one Document. A record source,
such as a CSV file, makes one Document per row.

`content_hash` is always the sha256 of `text`, whatever the loader. The
chunk offsets index `text`, so the hash names the text they point into.
`source_hash` is the sha256 of the raw source bytes, and it is kept apart so
that a change of converter output is still visible as a content change.

`id` is always the persisted Document node id for `document_key`. The
system computes it, and an explicit `id` must equal that value.

**Attributes:**

- [**text**](#agrag-common-data_models-document-Document-text) (<code>str</code>) – The document text. For a docling source, this holds the docling
  Markdown export. The chunker does not read it for a docling source: the
  chunks come from `sections`. The loaders leave it empty when
  `store_text` is off.
- [**title**](#agrag-common-data_models-document-Document-title) (<code>str</code>) – The document title.
- [**published_at**](#agrag-common-data_models-document-Document-published_at) (<code>date | None</code>) – The date the source says it was published, or `None`.
- [**content_date**](#agrag-common-data_models-document-Document-content_date) (<code>date | None</code>) – The date the content describes, or `None`.
- [**uri**](#agrag-common-data_models-document-Document-uri) (<code>str</code>) – The location of the source. It is not part of the node id, which
  follows `document_key`.
- [**source_format**](#agrag-common-data_models-document-Document-source_format) (<code>[SourceFormat](SourceFormat.md)</code>) – The format the loader used to read this document.
- [**family**](#agrag-common-data_models-document-Document-family) (<code>[DocumentFamily](DocumentFamily.md)</code>) – The shape of the source: one document per file, or one document per
  record.
- [**content_hash**](#agrag-common-data_models-document-Document-content_hash) (<code>str</code>) – The sha256 hex digest of `text` as UTF-8 bytes.
- [**loader_name**](#agrag-common-data_models-document-Document-loader_name) (<code>str</code>) – The name of the loader that produced this document, for example
  `"text"` or `"docling"`.
- [**loader_version**](#agrag-common-data_models-document-Document-loader_version) (<code>str | None</code>) – The version of the loader package. Does not affect the
  document id.
- [**encoding**](#agrag-common-data_models-document-Document-encoding) (<code>str | None</code>) – The text encoding. Text loaders set this field. Other loaders
  leave it empty.
- [**source_hash**](#agrag-common-data_models-document-Document-source_hash) (<code>str | None</code>) – The sha256 hex digest of the raw bytes of the source file.
  Every document read from a file sets this field. Inline text leaves it
  `None`.
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
- [**schema_name**](#agrag-common-data_models-document-Document-schema_name) (<code>str | None</code>) – The name of the schema of the run that wrote the document.
  `None` for a document that no run stamped.
- [**schema_version**](#agrag-common-data_models-document-Document-schema_version) (<code>str | None</code>) – The version string of that schema.
- [**schema_fingerprint**](#agrag-common-data_models-document-Document-schema_fingerprint) (<code>str | None</code>) – The structure hash of that schema (see
  `agrag.common.schema_fingerprint`).
- [**extraction_fingerprint**](#agrag-common-data_models-document-Document-extraction_fingerprint) (<code>str | None</code>) – The hash of the descriptions, the extraction
  settings and the model name of that run.

**Functions:**

- [**node_id_for**](#agrag-common-data_models-document-Document-node_id_for) – Compute the persisted Document graph node id.
- [**to_node_record**](#agrag-common-data_models-document-Document-to_node_record) – Return this document as a GraphStore write record for its graph node.

## `char_count` \{#agrag-common-data_models-document-Document-char_count}

```python
char_count: int
```

## `content_date` \{#agrag-common-data_models-document-Document-content_date}

```python
content_date: date | None = None
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

## `extraction_fingerprint` \{#agrag-common-data_models-document-Document-extraction_fingerprint}

```python
extraction_fingerprint: str | None = None
```

## `family` \{#agrag-common-data_models-document-Document-family}

```python
family: DocumentFamily
```

## `id` \{#agrag-common-data_models-document-Document-id}

```python
id: UUID | None = None
```

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

The id is keyed on `document_key`, not the content hash, so it stays
the same across content changes to the same logical document. Every
content version of a document shares one graph node with a changing
content hash.

**Parameters:**

- **document_key** (<code>str</code>) – The document's stable key.

**Returns:**

- <code>UUID</code> – The Document graph node id.

## `normalization` \{#agrag-common-data_models-document-Document-normalization}

```python
normalization: Normalization | None = None
```

## `published_at` \{#agrag-common-data_models-document-Document-published_at}

```python
published_at: date | None = None
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

## `schema_fingerprint` \{#agrag-common-data_models-document-Document-schema_fingerprint}

```python
schema_fingerprint: str | None = None
```

## `schema_name` \{#agrag-common-data_models-document-Document-schema_name}

```python
schema_name: str | None = None
```

## `schema_version` \{#agrag-common-data_models-document-Document-schema_version}

```python
schema_version: str | None = None
```

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
