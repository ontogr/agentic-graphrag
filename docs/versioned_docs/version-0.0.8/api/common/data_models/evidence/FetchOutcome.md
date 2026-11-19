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
- [**title**](#agrag-common-data_models-evidence-FetchOutcome-title) (<code>str | None</code>) – Stored document title, when readable.
- [**uri**](#agrag-common-data_models-evidence-FetchOutcome-uri) (<code>str | None</code>) – Valid HTTP(S) source URL, when available.
- [**location**](#agrag-common-data_models-evidence-FetchOutcome-location) (<code>[EvidenceLocation](EvidenceLocation.md) | None</code>) – Passage location, including page provenance when available.
- [**content_hash**](#agrag-common-data_models-evidence-FetchOutcome-content_hash) (<code>str | None</code>) – The full content hash of the version the text came from.
- [**status_of_version**](#agrag-common-data_models-evidence-FetchOutcome-status_of_version) (<code>[VersionStatus](VersionStatus.md) | None</code>) – Whether that version is current, when text is
  returned.
- [**observed_activation_seq**](#agrag-common-data_models-evidence-FetchOutcome-observed_activation_seq) (<code>int | None</code>) – The document activation sequence observed in
  the same read as the text, including for a superseded version.
- [**covered_range**](#agrag-common-data_models-evidence-FetchOutcome-covered_range) (<code>tuple\[int, int\] | None</code>) – The offsets of the returned text, when it is a text
  range. A partial range gives the covered part only.
- [**partial**](#agrag-common-data_models-evidence-FetchOutcome-partial) (<code>bool</code>) – True when the requested range was not fully covered by chunks.
- [**detail**](#agrag-common-data_models-evidence-FetchOutcome-detail) (<code>str | None</code>) – A short message for a malformed or failed id. It is None for an
  unavailable id, because the reason stays on the server side.
- [**citation_markdown**](#agrag-common-data_models-evidence-FetchOutcome-citation_markdown) (<code>str | None</code>) – Escaped source reference for a complete fetch, or None.
  Absolute HTTP(S) source URIs become links; other sources display as text.

## `citation_markdown` \{#agrag-common-data_models-evidence-FetchOutcome-citation_markdown}

```python
citation_markdown: str | None
```

Return a readable source reference only for complete fetched evidence.

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

## `location` \{#agrag-common-data_models-evidence-FetchOutcome-location}

```python
location: EvidenceLocation | None = None
```

## `observed_activation_seq` \{#agrag-common-data_models-evidence-FetchOutcome-observed_activation_seq}

```python
observed_activation_seq: int | None = None
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

## `title` \{#agrag-common-data_models-evidence-FetchOutcome-title}

```python
title: str | None = None
```

## `uri` \{#agrag-common-data_models-evidence-FetchOutcome-uri}

```python
uri: str | None = None
```
