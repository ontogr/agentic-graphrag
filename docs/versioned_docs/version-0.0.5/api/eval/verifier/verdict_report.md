---
title: agrag.eval.verifier.verdict_report
sidebar_label: verdict_report
---

# `agrag.eval.verifier.verdict_report` \{#agrag-eval-verifier-verdict_report}

```python
verdict_report(gold:Sequence[str], predicted:Sequence[str]) -> VerdictReport
```

Score predicted verdicts against gold verdicts.

**Parameters:**

- **gold** (<code>Sequence\[str\]</code>) – The gold label of each item.
- **predicted** (<code>Sequence\[str\]</code>) – The label of each item from `run_verifier`.

**Returns:**

- <code>[VerdictReport](VerdictReport.md)</code> – Per-class scores, macro F1, the confusion matrix and the error count.
