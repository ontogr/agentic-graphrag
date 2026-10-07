---
title: agrag.vectordb.pending
sidebar_label: pending
---

# `agrag.vectordb.pending` \{#agrag-vectordb-pending}

Pending-record bookkeeping shared by the VectorStore adapters.

A record written for an in-flight Cutover Job lands under a staging id, so a
committed record with the real id stays searchable until the job commits and
survives the job's rollback.

**Functions:**

- [**promote_record**](promote_record.md) – Return the committed record a staged record stands for.
- [**stage_records**](stage_records.md) – Return records ready to write for one job, or unchanged outside a job.

**Attributes:**

- [**PENDING_FLAG**](PENDING_FLAG.md) – Payload boolean that is true while a record belongs to an in-flight job.
- [**PENDING_JOB_KEY**](PENDING_JOB_KEY.md) – Payload key holding the id of the job that wrote a staged record.
- [**RESERVED_KEYS**](RESERVED_KEYS.md) – Payload keys the stores own; a caller payload may not use them.
- [**TARGET_ID_KEY**](TARGET_ID_KEY.md) – Payload key holding the real id a staged record is promoted to.
