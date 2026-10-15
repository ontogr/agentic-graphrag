---
title: agrag.agents.result.AgentRunResult
sidebar_label: AgentRunResult
---

# `agrag.agents.result.AgentRunResult` \{#agrag-agents-result-AgentRunResult}

Bases: <code>TypedDict</code>

Outcome, answer, evidence references and conversation for one run.

**Attributes:**

- [**answer**](#agrag-agents-result-AgentRunResult-answer) (<code>str</code>) –
- [**citations**](#agrag-agents-result-AgentRunResult-citations) (<code>list\[[FetchOutcome](../../common/data_models/evidence/FetchOutcome.md)\]</code>) –
- [**invalid_citations**](#agrag-agents-result-AgentRunResult-invalid_citations) (<code>list\[str\]</code>) –
- [**messages**](#agrag-agents-result-AgentRunResult-messages) (<code>list\[Any\]</code>) –
- [**status**](#agrag-agents-result-AgentRunResult-status) (<code>Literal['answered', 'insufficient_evidence', 'partial_retrieval', 'partial', 'recording_failed', 'budget_exhausted']</code>) –
- [**task**](#agrag-agents-result-AgentRunResult-task) (<code>[AgentTaskRef](AgentTaskRef.md)</code>) –

## `answer` \{#agrag-agents-result-AgentRunResult-answer}

```python
answer: str
```

## `citations` \{#agrag-agents-result-AgentRunResult-citations}

```python
citations: list[FetchOutcome]
```

## `invalid_citations` \{#agrag-agents-result-AgentRunResult-invalid_citations}

```python
invalid_citations: list[str]
```

## `messages` \{#agrag-agents-result-AgentRunResult-messages}

```python
messages: list[Any]
```

## `status` \{#agrag-agents-result-AgentRunResult-status}

```python
status: Literal['answered', 'insufficient_evidence', 'partial_retrieval', 'partial', 'recording_failed', 'budget_exhausted']
```

## `task` \{#agrag-agents-result-AgentRunResult-task}

```python
task: AgentTaskRef
```
