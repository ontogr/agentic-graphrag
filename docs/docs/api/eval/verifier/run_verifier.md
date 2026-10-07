---
title: agrag.eval.verifier.run_verifier
sidebar_label: run_verifier
---

# `agrag.eval.verifier.run_verifier` \{#agrag-eval-verifier-run_verifier}

```python
run_verifier(model:Any, items:Sequence[VerdictItem], *, concurrency:int = _CONCURRENCY) -> list[str]
```

Run the verifier over items and return one label per item.

A call that raises gives the label `ERROR`. It is wrong for every gold
class and shows in the report. It is never dropped.

**Parameters:**

- **model** (<code>Any</code>) – The chat model under test.
- **items** (<code>Sequence\[[VerdictItem](VerdictItem.md)\]</code>) – The fixed inputs.
- **concurrency** (<code>int</code>) – The most calls that run at once. Lower it for an endpoint
  that limits concurrent requests.

**Returns:**

- <code>list\[str\]</code> – One verdict label per item, in the order of `items`.

**Raises:**

- <code>ValueError</code> – `concurrency` is less than 1.
