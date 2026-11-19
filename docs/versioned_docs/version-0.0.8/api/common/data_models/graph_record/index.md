---
title: agrag.common.data_models.graph_record
sidebar_label: graph_record
---

# `agrag.common.data_models.graph_record` \{#agrag-common-data_models-graph_record}

Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity and Relation
domain model that resolution will eventually produce. See the future
storage and merge-mechanics work this decouples from.

Pending-visibility convention: a Cutover Job tags each node and edge it
creates with `_pending_job_id` (the job id). A job writes only rows it
created. A write that reaches a committed row is not applied: the store
reports that record as unwritten and holds it in a `DeferredWrites` list.
The commit transaction replays the list after the job flips to committed, so
a committed row changes only together with the commit. `GraphStore` writes
the tag when the caller passes `pending_job_id` to an upsert, so records
never carry it and the validators below reject it. Retrieval query builders
exclude tagged rows with `pending_filter_clause`.

Rollback deletes the rows a job tagged. Committed rows are never tagged by a
job, so rollback cannot delete data committed earlier and leaves those rows
as they were.

**Classes:**

- [**DeferredWrites**](DeferredWrites.md) – Writes over committed rows, held until the job's commit transaction.
- [**NodeRecord**](NodeRecord.md) – One graph node, ready to write.
- [**RelationRecord**](RelationRecord.md) – One graph relationship, ready to write.
- [**UpsertFailure**](UpsertFailure.md) – One record that failed to write within a bulk upsert call.
- [**UpsertResult**](UpsertResult.md) – Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

**Attributes:**

- [**PENDING_JOB_ID_PROPERTY**](PENDING_JOB_ID_PROPERTY.md) – Graph property marking a node or edge as created by an in-flight job.
