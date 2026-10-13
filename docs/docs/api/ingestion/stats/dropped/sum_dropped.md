---
title: agrag.ingestion.stats.dropped.sum_dropped
sidebar_label: sum_dropped
---

# `agrag.ingestion.stats.dropped.sum_dropped` \{#agrag-ingestion-stats-dropped-sum_dropped}

```python
sum_dropped(groups:Iterable[Sequence[DroppedCount]]) -> list[DroppedCount]
```

Sum dropped counts from several ingestion jobs.

**Parameters:**

- **groups** (<code>Iterable\[Sequence\[[DroppedCount](DroppedCount.md)\]\]</code>) – One list of counts per job.

**Returns:**

- <code>list\[[DroppedCount](DroppedCount.md)\]</code> – One sorted entry per distinct kind, label and reason.
