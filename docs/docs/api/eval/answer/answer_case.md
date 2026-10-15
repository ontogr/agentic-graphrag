---
title: agrag.eval.answer.answer_case
sidebar_label: answer_case
---

# `agrag.eval.answer.answer_case` \{#agrag-eval-answer-answer_case}

```python
answer_case(question:str, result:AgentRunResult, reference:str) -> LLMTestCase
```

Build the test case that every answer-quality metric scores.

`retrieval_context` holds the fetched evidence. `metadata["citations"]`
maps each evidence id to its text for `CitationAccuracyMetric`.

**Parameters:**

- **question** (<code>str</code>) – The question the agent answered.
- **result** (<code>[AgentRunResult](../../agents/result/AgentRunResult.md)</code>) – The result of `agent.ainvoke` for that question.
- **reference** (<code>str</code>) – The reference answer.

**Returns:**

- <code>LLMTestCase</code> – The test case with the answer and rendered evidence.
