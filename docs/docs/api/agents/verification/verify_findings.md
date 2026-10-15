---
title: agrag.agents.verification.verify_findings
sidebar_label: verify_findings
---

# `agrag.agents.verification.verify_findings` \{#agrag-agents-verification-verify_findings}

```python
verify_findings(model:Any, question:str, sub_questions:Sequence[str], findings:str) -> VerificationResult
```

Run the verifier on fixed inputs and return its structured verdict.

Runs the fixed-input verifier used by the calibration evaluator. The default
task agent does not use this helper or a verifier subagent.

**Parameters:**

- **model** (<code>Any</code>) – A LangChain chat model.
- **question** (<code>str</code>) – The original question.
- **sub_questions** (<code>Sequence\[str\]</code>) – The sub-questions the question was split into.
- **findings** (<code>str</code>) – The findings with citation keys such as `E1`,
  and the evidence text for each key.

**Returns:**

- <code>[VerificationResult](VerificationResult.md)</code> – The verifier's verdict.

**Raises:**

- <code>ValueError</code> – The model returned no verdict, after the agent asked again a
  few times.
