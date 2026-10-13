---
title: agrag.agents.verification.VerificationResult
sidebar_label: VerificationResult
---

# `agrag.agents.verification.VerificationResult` \{#agrag-agents-verification-VerificationResult}

Bases: <code>BaseModel</code>

The verifier's structured verdict on the researcher's findings.

The verifier returns this through its `response_format`, so the
planner reads a typed verdict out of the task tool's result instead
of parsing free-form prose.

**Attributes:**

- [**reasoning**](#agrag-agents-verification-VerificationResult-reasoning) (<code>str</code>) – What the independent per-sub-question checks found,
  written before the verdict is decided.
- [**status**](#agrag-agents-verification-VerificationResult-status) (<code>Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']</code>) – The overall verdict. `PASS` means every sub-question
  has supporting evidence and nothing contradicts; a re-delegation
  after this verdict is not a retry. `INSUFFICIENT` means one
  or more sub-questions lack supporting evidence, listed in
  `missing_evidence`. `CONTRADICTORY` means cited evidence
  conflicts, which re-researching cannot resolve.
- [**missing_evidence**](#agrag-agents-verification-VerificationResult-missing_evidence) (<code>list\[str\]</code>) – The sub-questions and evidence gaps to close,
  filled when the status is `INSUFFICIENT`.

## `missing_evidence` \{#agrag-agents-verification-VerificationResult-missing_evidence}

```python
missing_evidence: list[str] = Field(default_factory=list)
```

## `reasoning` \{#agrag-agents-verification-VerificationResult-reasoning}

```python
reasoning: str
```

## `status` \{#agrag-agents-verification-VerificationResult-status}

```python
status: Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']
```
