---
title: agrag.agents.tools.aggregate.compute_over_evidence
sidebar_label: compute_over_evidence
---

# `agrag.agents.tools.aggregate.compute_over_evidence` \{#agrag-agents-tools-aggregate-compute_over_evidence}

```python
compute_over_evidence(operation:Literal['count', 'sum', 'compare'], values:list[float], *, compare_op:Literal['gt', 'lt', 'eq'] | None = None) -> str
```

Compute a count, a sum, or a comparison over numbers you supply.

Use this instead of doing arithmetic in your head when a question
asks how many, how much in total, or whether one figure exceeds
another. It never queries the graph: pass the numbers you have
already read from earlier tool results.

**Parameters:**

- **operation** (<code>Literal['count', 'sum', 'compare']</code>) – "count" for how many values you supplied, "sum" for
  their total, "compare" for a comparison between exactly two
  of them.
- **values** (<code>list\[float\]</code>) – The numbers to compute over, in the order you read them.
- **compare_op** (<code>Literal['gt', 'lt', 'eq'] | None</code>) – Required for "compare": "gt" for values[0] greater
  than values[1], "lt" for less than, "eq" for equal.
