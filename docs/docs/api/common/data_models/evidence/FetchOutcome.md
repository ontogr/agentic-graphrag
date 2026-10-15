---
title: agrag.common.data_models.evidence.FetchOutcome
sidebar_label: FetchOutcome
---

# `agrag.common.data_models.evidence.FetchOutcome` \{#agrag-common-data_models-evidence-FetchOutcome}

Bases: <code>BaseModel</code>

The result of fetching one evidence id.

**Attributes:**

- [**evidence_id**](#agrag-common-data_models-evidence-FetchOutcome-evidence_id) (<code>str</code>) – The id that was requested, as given.
- [**status**](#agrag-common-data_models-evidence-FetchOutcome-status) (<code>[FetchStatus](FetchStatus.md)</code>) – The outcome of the fetch.
- [**text**](#agrag-common-data_models-evidence-FetchOutcome-text) (<code>str | None</code>) – The returned text, or None when no text is returned.
- [**reference**](#agrag-common-data_models-evidence-FetchOutcome-reference) (<code>[EvidenceReference](EvidenceReference.md) | None</code>) – The decoded reference, or None for a malformed id.
- [**document_key**](#agrag-common-data_models-evidence-FetchOutcome-document_key) (<code>str | None</code>) – The key of the document, when the document is readable.
- [**content_hash**](#agrag-common-data_models-evidence-FetchOutcome-content_hash) (<code>str | None</code>) – The full content hash of the version the text came from.
- [**status_of_version**](#agrag-common-data_models-evidence-FetchOutcome-status_of_version) (<code>[VersionStatus](VersionStatus.md) | None</code>) – Whether that version is current, when text is
  returned.
- [**covered_range**](#agrag-common-data_models-evidence-FetchOutcome-covered_range) (<code>tuple\[int, int\] | None</code>) – The offsets of the returned text, when it is a text
  range. A partial range gives the covered part only.
- [**partial**](#agrag-common-data_models-evidence-FetchOutcome-partial) (<code>bool</code>) – True when the requested range was not fully covered by chunks.
- [**detail**](#agrag-common-data_models-evidence-FetchOutcome-detail) (<code>str | None</code>) – A short message for a malformed or failed id. It is None for an
  unavailable id, because the reason stays on the server side.

## `content_hash` \{#agrag-common-data_models-evidence-FetchOutcome-content_hash}

```python
content_hash: str | None = None
```

## `covered_range` \{#agrag-common-data_models-evidence-FetchOutcome-covered_range}

```python
covered_range: tuple[int, int] | None = None
```

## `detail` \{#agrag-common-data_models-evidence-FetchOutcome-detail}

```python
detail: str | None = None
```

## `document_key` \{#agrag-common-data_models-evidence-FetchOutcome-document_key}

```python
document_key: str | None = None
```

## `evidence_id` \{#agrag-common-data_models-evidence-FetchOutcome-evidence_id}

```python
evidence_id: str
```

## `partial` \{#agrag-common-data_models-evidence-FetchOutcome-partial}

```python
partial: bool = False
```

## `reference` \{#agrag-common-data_models-evidence-FetchOutcome-reference}

```python
reference: EvidenceReference | None = None
```

## `status` \{#agrag-common-data_models-evidence-FetchOutcome-status}

```python
status: FetchStatus
```

## `status_of_version` \{#agrag-common-data_models-evidence-FetchOutcome-status_of_version}

```python
status_of_version: VersionStatus | None = None
```

## `text` \{#agrag-common-data_models-evidence-FetchOutcome-text}

```python
text: str | None = None
```
