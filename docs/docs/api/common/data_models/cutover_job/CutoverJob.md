---
title: agrag.common.data_models.cutover_job.CutoverJob
sidebar_label: CutoverJob
---

# `agrag.common.data_models.cutover_job.CutoverJob` \{#agrag-common-data_models-cutover_job-CutoverJob}

Bases: <code>[DataPoint](../data_point/DataPoint.md)</code>

Crash-recoverable state for one add/update/delete_document call.

**Attributes:**

- [**document_key**](#agrag-common-data_models-cutover_job-CutoverJob-document_key) (<code>str</code>) – The document this job mutates. Unique among
  non-terminal jobs (enforced by a graph constraint plus lease
  fencing, not the constraint alone).
- [**verb**](#agrag-common-data_models-cutover_job-CutoverJob-verb) (<code>Literal['add', 'update', 'delete_document']</code>) – Which public method created this job.
- [**status**](#agrag-common-data_models-cutover_job-CutoverJob-status) (<code>[CutoverJobStatus](CutoverJobStatus.md)</code>) – Current phase, see CutoverJobStatus.
- [**affected_entity_ids**](#agrag-common-data_models-cutover_job-CutoverJob-affected_entity_ids) (<code>list\[UUID\]</code>) – The snapshot taken before any pending write
  began — the only entities pruning may remove.
- [**component_seed_ids**](#agrag-common-data_models-cutover_job-CutoverJob-component_seed_ids) (<code>list\[UUID\]</code>) – One member id per match component the job
  rebuilt, recorded at commit. The cleanup phase rebuilds
  each component's resolved entity from these, in addition to
  pruning, so a resumed job can replace the resolved entity
  the commit left in place.
- [**lease_token**](#agrag-common-data_models-cutover_job-CutoverJob-lease_token) (<code>UUID</code>) – Current lease holder's fencing token.
- [**lease_expires_at**](#agrag-common-data_models-cutover_job-CutoverJob-lease_expires_at) (<code>datetime</code>) – When the current lease expires.

**Functions:**

- [**to_node_record**](#agrag-common-data_models-cutover_job-CutoverJob-to_node_record) – Return this job as a graph write record.

## `affected_entity_ids` \{#agrag-common-data_models-cutover_job-CutoverJob-affected_entity_ids}

```python
affected_entity_ids: list[UUID] = Field(default_factory=list)
```

## `component_seed_ids` \{#agrag-common-data_models-cutover_job-CutoverJob-component_seed_ids}

```python
component_seed_ids: list[UUID] = Field(default_factory=list)
```

## `created_at` \{#agrag-common-data_models-cutover_job-CutoverJob-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `document_key` \{#agrag-common-data_models-cutover_job-CutoverJob-document_key}

```python
document_key: str
```

## `id` \{#agrag-common-data_models-cutover_job-CutoverJob-id}

```python
id: UUID
```

## `lease_expires_at` \{#agrag-common-data_models-cutover_job-CutoverJob-lease_expires_at}

```python
lease_expires_at: datetime
```

## `lease_token` \{#agrag-common-data_models-cutover_job-CutoverJob-lease_token}

```python
lease_token: UUID
```

## `metadata` \{#agrag-common-data_models-cutover_job-CutoverJob-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

## `status` \{#agrag-common-data_models-cutover_job-CutoverJob-status}

```python
status: CutoverJobStatus
```

## `to_node_record` \{#agrag-common-data_models-cutover_job-CutoverJob-to_node_record}

```python
to_node_record() -> NodeRecord
```

Return this job as a graph write record.

## `verb` \{#agrag-common-data_models-cutover_job-CutoverJob-verb}

```python
verb: Literal['add', 'update', 'delete_document']
```
