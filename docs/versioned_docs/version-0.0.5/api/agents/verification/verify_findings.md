---
title: agrag.agents.verification.verify_findings
sidebar_label: verify_findings
---

# `agrag.agents.verification.verify_findings` \{#agrag-agents-verification-verify_findings}

```python
verify_findings(model:Any, question:str, sub_questions:Sequence[str], findings:str) -> VerificationResult
```

Run the verifier on fixed inputs and return its structured verdict.

Runs the agent that the verifier subagent runs: `VERIFIER_SYSTEM` as the
system prompt, one user message, and `VerificationResult` as the response
format. The response format is handled as it is in a full run, so the model
must answer through the verdict tool. This calibrates the verifier prompt and
model on a fixed input format. It does not test the text the planner writes
when it delegates to the verifier.

**Parameters:**

- **model** (<code>Any</code>) – A LangChain chat model.
- **question** (<code>str</code>) – The original question.
- **sub_questions** (<code>Sequence\[str\]</code>) – The sub-questions the question was split into.
- **findings** (<code>str</code>) – The researcher's findings with citation keys such as `E1`,
  and the evidence text for each key.

**Returns:**

- <code>[VerificationResult](VerificationResult.md)</code> – The verifier's verdict.

**Raises:**

- <code>ValueError</code> – The model returned no verdict, after the agent asked again a
  few times.
