---
title: agrag.eval.parse_json_case
sidebar_label: parse_json_case
---

# `agrag.eval.parse_json_case` \{#agrag-eval-parse_json_case}

```python
parse_json_case(test_case:LLMTestCase, model:type[ModelT]) -> tuple[ModelT, ModelT]
```

Read the `(actual, expected)` models back from a JSON test case.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – A case built by `to_json_case`.
- **model** (<code>type\[[ModelT](adapter/ModelT.md)\]</code>) – The pydantic model both outputs were serialized from.
