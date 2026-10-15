---
title: agrag.common.data_models.decision.DocumentSupport
sidebar_label: DocumentSupport
---

# `agrag.common.data_models.decision.DocumentSupport` \{#agrag-common-data_models-decision-DocumentSupport}

Bases: <code>BaseModel</code>

A stored document support, with the passage it names.

**Attributes:**

- [**kind**](#agrag-common-data_models-decision-DocumentSupport-kind) (<code>Literal\[[DOCUMENT](SupportKind.md#agrag-common-data_models-decision-SupportKind-DOCUMENT)\]</code>) – Always `document`.
- [**evidence_id**](#agrag-common-data_models-decision-DocumentSupport-evidence_id) (<code>str</code>) – The evidence id the caller cited.
- [**document_key**](#agrag-common-data_models-decision-DocumentSupport-document_key) (<code>str</code>) – The stable key of the cited document.
- [**document_node_id**](#agrag-common-data_models-decision-DocumentSupport-document_node_id) (<code>UUID</code>) – The id of the Document node.
- [**content_hash_prefix**](#agrag-common-data_models-decision-DocumentSupport-content_hash_prefix) (<code>str</code>) – The first 16 hex characters of the cited version.
- [**reference_kind**](#agrag-common-data_models-decision-DocumentSupport-reference_kind) (<code>[EvidenceKind](../evidence/EvidenceKind.md)</code>) – Whether the id names a span or a chunk.
- [**char_start**](#agrag-common-data_models-decision-DocumentSupport-char_start) (<code>int | None</code>) – Start offset of a span, or None for a chunk.
- [**char_end**](#agrag-common-data_models-decision-DocumentSupport-char_end) (<code>int | None</code>) – End offset of a span, or None for a chunk.
- [**chunk_id**](#agrag-common-data_models-decision-DocumentSupport-chunk_id) (<code>UUID | None</code>) – The chunk id of a chunk reference, or None for a span.
- [**recorded_activation_seq**](#agrag-common-data_models-decision-DocumentSupport-recorded_activation_seq) (<code>int | None</code>) – The document's activation sequence number
  when the decision was recorded.

## `char_end` \{#agrag-common-data_models-decision-DocumentSupport-char_end}

```python
char_end: int | None = None
```

## `char_start` \{#agrag-common-data_models-decision-DocumentSupport-char_start}

```python
char_start: int | None = None
```

## `chunk_id` \{#agrag-common-data_models-decision-DocumentSupport-chunk_id}

```python
chunk_id: UUID | None = None
```

## `content_hash` \{#agrag-common-data_models-decision-DocumentSupport-content_hash}

```python
content_hash: str
```

## `content_hash_prefix` \{#agrag-common-data_models-decision-DocumentSupport-content_hash_prefix}

```python
content_hash_prefix: str
```

## `document_key` \{#agrag-common-data_models-decision-DocumentSupport-document_key}

```python
document_key: str
```

## `document_node_id` \{#agrag-common-data_models-decision-DocumentSupport-document_node_id}

```python
document_node_id: UUID
```

## `evidence_id` \{#agrag-common-data_models-decision-DocumentSupport-evidence_id}

```python
evidence_id: str
```

## `kind` \{#agrag-common-data_models-decision-DocumentSupport-kind}

```python
kind: Literal[SupportKind.DOCUMENT]
```

## `model_config` \{#agrag-common-data_models-decision-DocumentSupport-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded_activation_seq` \{#agrag-common-data_models-decision-DocumentSupport-recorded_activation_seq}

```python
recorded_activation_seq: int | None = None
```

## `reference_kind` \{#agrag-common-data_models-decision-DocumentSupport-reference_kind}

```python
reference_kind: EvidenceKind
```
