---
title: agrag.evidence.fetch.fetch_evidence
sidebar_label: fetch_evidence
---

# `agrag.evidence.fetch.fetch_evidence` \{#agrag-evidence-fetch-fetch_evidence}

```python
fetch_evidence(store:GraphStore, evidence_ids:Sequence[str], *, scope:frozenset[str], max_chars:int, timeout:float | None = None) -> list[FetchOutcome]
```

Return the text of each evidence id, in the order given.

A span id returns the text of its range. Fetch reads the chunks of one chunk
set for the content hash in the id, so the range is never assembled from two
sets. A range that no chunk covers is cut to the covered part, which is marked
`partial`. Text is never padded. An id that names no readable evidence gives
`unavailable`. A missing id and an id outside the scope give the same
outcome. A chunk reference returns the stored text of that chunk.

The status of a version is `current` when the id's content hash matches the
document's current content hash. Older content remains fetchable as
`superseded` while the source is live and retained. Soft deletion hides
all text for the source; purge removes it.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to read.
- **evidence_ids** (<code>Sequence\[str\]</code>) – Evidence ids to fetch.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents the caller may read. An empty scope makes
  every id unavailable.
- **max_chars** (<code>int</code>) – The most characters returned for each id. Must be positive.
  Longer text is cut and marked `truncated`.
- **timeout** (<code>float | None</code>) – Server-side transaction timeout in seconds for each store read.
  None uses the server's default.

**Returns:**

- <code>list\[[FetchOutcome](../../common/data_models/evidence/FetchOutcome.md)\]</code> – One outcome for each id, in the same order.

**Raises:**

- <code>ValueError</code> – `max_chars` is not positive.
