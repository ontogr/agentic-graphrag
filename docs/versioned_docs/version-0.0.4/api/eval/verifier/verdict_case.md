---
title: agrag.eval.verifier.verdict_case
sidebar_label: verdict_case
---

# `agrag.eval.verifier.verdict_case` \{#agrag-eval-verifier-verdict_case}

```python
verdict_case(item:VerdictItem, predicted:str) -> LLMTestCase
```

Build a test case with the predicted and the gold verdict.

**Parameters:**

- **item** (<code>[VerdictItem](VerdictItem.md)</code>) – The fixed input.
- **predicted** (<code>str</code>) – The label from `run_verifier`.

**Returns:**

- <code>LLMTestCase</code> – An `LLMTestCase` with the question, predicted verdict and gold verdict.
