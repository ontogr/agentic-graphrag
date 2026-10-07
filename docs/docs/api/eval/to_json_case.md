---
title: agrag.eval.to_json_case
sidebar_label: to_json_case
---

# `agrag.eval.to_json_case` \{#agrag-eval-to_json_case}

```python
to_json_case(input:str, actual:BaseModel, expected:BaseModel) -> LLMTestCase
```

Build a test case that carries structured data as JSON.

`LLMTestCase` has no field for structured gold data, so both models are
serialized to JSON in `actual_output` and `expected_output`. The JSON
also shows in DeepEval reports.

**Parameters:**

- **input** (<code>str</code>) – The input text, such as a question or a chunk.
- **actual** (<code>BaseModel</code>) – The system output.
- **expected** (<code>BaseModel</code>) – The gold data.
