---
title: agrag.common.data_models.evidence.SourceStatus
sidebar_label: SourceStatus
---

# `agrag.common.data_models.evidence.SourceStatus` \{#agrag-common-data_models-evidence-SourceStatus}

Bases: <code>BaseModel</code>

The committed version, active job and index state for one source.

**Attributes:**

- [**document_key**](#agrag-common-data_models-evidence-SourceStatus-document_key) (<code>str</code>) – Stable source key requested by the caller.
- [**state**](#agrag-common-data_models-evidence-SourceStatus-state) (<code>[SourceState](SourceState.md)</code>) – Lifecycle state derived from committed rows and the latest job.
- [**content_hash**](#agrag-common-data_models-evidence-SourceStatus-content_hash) (<code>str | None</code>) – Hash of the committed current version, if any.
- [**activation_seq**](#agrag-common-data_models-evidence-SourceStatus-activation_seq) (<code>int | None</code>) – Sequence number of the latest committed activation.
- [**version_id**](#agrag-common-data_models-evidence-SourceStatus-version_id) (<code>str | None</code>) – Version id on the current open `HAS_PART` edges.
- [**job_id**](#agrag-common-data_models-evidence-SourceStatus-job_id) (<code>str | None</code>) – Id of the latest incomplete cutover job.
- [**job_status**](#agrag-common-data_models-evidence-SourceStatus-job_status) (<code>str | None</code>) – Lifecycle status of that job.
- [**lease_expires_at**](#agrag-common-data_models-evidence-SourceStatus-lease_expires_at) (<code>str | None</code>) – Lease expiry timestamp rendered as text.
- [**job_age_seconds**](#agrag-common-data_models-evidence-SourceStatus-job_age_seconds) (<code>float | None</code>) – Age of the latest incomplete job.
- [**job_error**](#agrag-common-data_models-evidence-SourceStatus-job_error) (<code>str | None</code>) – Stored job error or expired-lease reason.
- [**indexes**](#agrag-common-data_models-evidence-SourceStatus-indexes) (<code>list\[[SourceIndexStatus](SourceIndexStatus.md)\]</code>) – Full-text and vector index states used by discovery.

## `activation_seq` \{#agrag-common-data_models-evidence-SourceStatus-activation_seq}

```python
activation_seq: int | None = None
```

## `content_hash` \{#agrag-common-data_models-evidence-SourceStatus-content_hash}

```python
content_hash: str | None = None
```

## `document_key` \{#agrag-common-data_models-evidence-SourceStatus-document_key}

```python
document_key: str
```

## `indexes` \{#agrag-common-data_models-evidence-SourceStatus-indexes}

```python
indexes: list[SourceIndexStatus] = Field(default_factory=list)
```

## `job_age_seconds` \{#agrag-common-data_models-evidence-SourceStatus-job_age_seconds}

```python
job_age_seconds: float | None = None
```

## `job_error` \{#agrag-common-data_models-evidence-SourceStatus-job_error}

```python
job_error: str | None = None
```

## `job_id` \{#agrag-common-data_models-evidence-SourceStatus-job_id}

```python
job_id: str | None = None
```

## `job_status` \{#agrag-common-data_models-evidence-SourceStatus-job_status}

```python
job_status: str | None = None
```

## `lease_expires_at` \{#agrag-common-data_models-evidence-SourceStatus-lease_expires_at}

```python
lease_expires_at: str | None = None
```

## `state` \{#agrag-common-data_models-evidence-SourceStatus-state}

```python
state: SourceState
```

## `version_id` \{#agrag-common-data_models-evidence-SourceStatus-version_id}

```python
version_id: str | None = None
```
