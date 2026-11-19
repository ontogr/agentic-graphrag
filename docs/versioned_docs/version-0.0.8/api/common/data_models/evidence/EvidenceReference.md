---
title: agrag.common.data_models.evidence.EvidenceReference
sidebar_label: EvidenceReference
---

# `agrag.common.data_models.evidence.EvidenceReference` \{#agrag-common-data_models-evidence-EvidenceReference}

Bases: <code>BaseModel</code>

A stable pointer to passage text of one version of a document.

The reference holds only the first 16 hex characters of the content hash,
because that is what the evidence id carries. Fetch results give the full
hash.

**Attributes:**

- [**kind**](#agrag-common-data_models-evidence-EvidenceReference-kind) (<code>[EvidenceKind](EvidenceKind.md)</code>) – Whether the reference names a span or a chunk.
- [**document_node_id**](#agrag-common-data_models-evidence-EvidenceReference-document_node_id) (<code>UUID</code>) – The id of the Document graph node.
- [**content_hash_prefix**](#agrag-common-data_models-evidence-EvidenceReference-content_hash_prefix) (<code>str</code>) – The first 16 lowercase hex characters of the
  sha256 content hash of the version.
- [**char_start**](#agrag-common-data_models-evidence-EvidenceReference-char_start) (<code>int | None</code>) – The start offset of a span, in the document text.
- [**char_end**](#agrag-common-data_models-evidence-EvidenceReference-char_end) (<code>int | None</code>) – The exclusive end offset of a span, in the document text.
- [**chunk_id**](#agrag-common-data_models-evidence-EvidenceReference-chunk_id) (<code>UUID | None</code>) – The id of the chunk node of a chunk reference.

## `char_end` \{#agrag-common-data_models-evidence-EvidenceReference-char_end}

```python
char_end: int | None = None
```

## `char_start` \{#agrag-common-data_models-evidence-EvidenceReference-char_start}

```python
char_start: int | None = None
```

## `chunk_id` \{#agrag-common-data_models-evidence-EvidenceReference-chunk_id}

```python
chunk_id: UUID | None = None
```

## `content_hash_prefix` \{#agrag-common-data_models-evidence-EvidenceReference-content_hash_prefix}

```python
content_hash_prefix: str = Field(pattern='^[0-9a-f]{16}$')
```

## `document_node_id` \{#agrag-common-data_models-evidence-EvidenceReference-document_node_id}

```python
document_node_id: UUID
```

## `kind` \{#agrag-common-data_models-evidence-EvidenceReference-kind}

```python
kind: EvidenceKind
```
