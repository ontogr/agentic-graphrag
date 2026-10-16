---
title: agrag.evidence.render.render_citations
sidebar_label: render_citations
---

# `agrag.evidence.render.render_citations` \{#agrag-evidence-render-render_citations}

```python
render_citations(answer:str, valid_ids:Sequence[str], fetched:Sequence[FetchOutcome]) -> tuple[str, list[FetchOutcome]]
```

Replace validated inline IDs with readable Markdown source references.

Call after `check_citations` with only its valid IDs and complete fetches
from the same scope. This function formats references, not claim support.
Mixed invalid groups and existing Markdown links are left unchanged. Local
sources become non-link references; no web URL is inferred from an ID.
A narrower valid span uses its fetched parent's metadata while labeling its
own offsets. The parent outcome remains unchanged in the source list.

**Parameters:**

- **answer** (<code>str</code>) – Answer containing square-bracket evidence IDs, alone or grouped.
- **valid_ids** (<code>Sequence\[str\]</code>) – IDs accepted by the final citation validation pass.
- **fetched** (<code>Sequence\[[FetchOutcome](../../common/data_models/evidence/FetchOutcome.md)\]</code>) – Actual fetch outcomes from that run or session.

**Returns:**

- <code>tuple\[str, list\[[FetchOutcome](../../common/data_models/evidence/FetchOutcome.md)\]\]</code> – Markdown answer and deduplicated fetched sources in citation order.
