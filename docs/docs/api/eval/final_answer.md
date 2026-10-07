---
title: agrag.eval.final_answer
sidebar_label: final_answer
---

# `agrag.eval.final_answer` \{#agrag-eval-final_answer}

```python
final_answer(result:AgentRunResult) -> str
```

Return the text of the last assistant message in an agent run.

Handles message dicts and LangChain message objects, and content that is a
string or a list of blocks. Only text blocks count.

**Parameters:**

- **result** (<code>[AgentRunResult](../agents/result/AgentRunResult.md)</code>) – The result of `agent.ainvoke`.

**Raises:**

- <code>ValueError</code> – The run holds no assistant message.
