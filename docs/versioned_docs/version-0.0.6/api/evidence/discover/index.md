---
title: agrag.evidence.discover
sidebar_label: discover
---

# `agrag.evidence.discover` \{#agrag-evidence-discover}

Find visible passages by full-text search, vector search, or both.

A passage is a chunk. Only current text is visible: a chunk needs an open
`HAS_PART` edge, must not be written by an in-flight job, and must belong to a
document in the caller's scope. Those rules are part of each search query, so
out-of-scope and superseded chunks never take a result slot.

**Functions:**

- [**discover**](discover-ref.md) – Find up to `limit` visible passages that match a query.
- [**reciprocal_rank_fusion**](reciprocal_rank_fusion.md) – Fuse ranked id lists into one score per id.

**Attributes:**

- [**RRF_CONSTANT**](RRF_CONSTANT.md) –
