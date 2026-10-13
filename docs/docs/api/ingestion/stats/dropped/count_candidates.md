---
title: agrag.ingestion.stats.dropped.count_candidates
sidebar_label: count_candidates
---

# `agrag.ingestion.stats.dropped.count_candidates` \{#agrag-ingestion-stats-dropped-count_candidates}

```python
count_candidates(candidates:Iterable[CandidateRecord]) -> list[DroppedCount]
```

Count extractor candidates by kind, label and reason.

**Parameters:**

- **candidates** (<code>Iterable\[[CandidateRecord](../../../common/data_models/candidate/CandidateRecord.md)\]</code>) – Extractor candidates. Each record contributes its count.

**Returns:**

- <code>list\[[DroppedCount](DroppedCount.md)\]</code> – One sorted entry per distinct kind, label and reason.
