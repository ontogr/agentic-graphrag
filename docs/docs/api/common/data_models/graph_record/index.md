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
committed data never carries this key. `GraphStore` writes the tag when
the caller passes `pending_job_id` to an upsert, so records never carry
it and the validators below reject it. Retrieval query builders exclude
tagged rows with `pending_filter_clause`. Vector stores keep a job's
records under staging ids with a `_pending` flag and the job id in the
payload, and promote them to their real ids at commit.

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

**Attributes:**

- [**PENDING_JOB_ID_PROPERTY**](PENDING_JOB_ID_PROPERTY.md) – Graph property marking a node or edge as created by an in-flight job.
