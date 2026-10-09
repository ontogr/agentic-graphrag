---
title: agrag.common.data_models.graph_record
sidebar_label: graph_record
---

# `agrag.common.data_models.graph_record` \{#agrag-common-data_models-graph_record}

Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity/Relation
domain model resolution will eventually produce. See the future
storage/merge-mechanics work this decouples from.

Pending-visibility convention: a node or edge *created* by an in-flight
Cutover Job carries `_pending_job_id` (the job's id) in its properties;
committed data never carries this key. Retrieval query builders exclude
such rows with `pending_filter_clause`. Vector-store payloads mirror the
tag as an explicit boolean `_pending` field, cleared at commit, because
payload filters match on present values rather than key absence.

The tag is written with `ON CREATE SET`, so a job that writes over a
row that already exists leaves it untagged. Such a row was already
visible before the job started and stays visible; the job's rollback,
which deletes tagged rows, therefore cannot delete data a caller
committed earlier.

**Classes:**

- [**NodeRecord**](NodeRecord.md) – One graph node, ready to write.
- [**RelationRecord**](RelationRecord.md) – One graph relationship, ready to write.
- [**UpsertFailure**](UpsertFailure.md) – One record that failed to write within a bulk upsert call.
- [**UpsertResult**](UpsertResult.md) – Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

**Functions:**

- [**tag_pending**](tag_pending.md) – Stamp a write record with the Cutover Job that is writing it.

**Attributes:**

- [**PENDING_JOB_ID_PROPERTY**](PENDING_JOB_ID_PROPERTY.md) – Graph property marking a node or edge as created by an in-flight job.
