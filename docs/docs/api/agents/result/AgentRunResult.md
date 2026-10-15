---
title: agrag.agents.result.AgentRunResult
sidebar_label: AgentRunResult
---

# `agrag.agents.result.AgentRunResult` \{#agrag-agents-result-AgentRunResult}

Bases: <code>TypedDict</code>

Outcome, answer, evidence references and conversation for one run.

**Attributes:**

- [**recording_failures**](#agrag-agents-result-AgentRunResult-recording_failures) (<code>list\[str\]</code>) – Descriptions of task writes that did not complete.

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

## `recording_failures` \{#agrag-agents-result-AgentRunResult-recording_failures}

```python
recording_failures: list[str]
```

## `status` \{#agrag-agents-result-AgentRunResult-status}

```python
status: Literal['answered', 'insufficient_evidence', 'partial_retrieval', 'partial', 'recording_failed', 'budget_exhausted']
```

## `task` \{#agrag-agents-result-AgentRunResult-task}

```python
task: AgentTaskRef
```
