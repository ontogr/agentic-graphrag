---
title: agrag.eval.verdict_case
sidebar_label: verdict_case
---

# `agrag.eval.verdict_case` \{#agrag-eval-verdict_case}

```python
verdict_case(item:VerdictItem, predicted:str) -> LLMTestCase
```

Build a test case with the predicted and the gold verdict.

**Parameters:**

- **item** (<code>[VerdictItem](verifier/VerdictItem.md)</code>) – The fixed input.
- **predicted** (<code>str</code>) – The label from `run_verifier`.

**Returns:**

- <code>LLMTestCase</code> – An `LLMTestCase` with the question, predicted verdict and gold verdict.
