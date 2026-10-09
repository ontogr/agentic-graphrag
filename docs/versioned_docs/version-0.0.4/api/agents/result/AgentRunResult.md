---
title: agrag.agents.result.AgentRunResult
sidebar_label: AgentRunResult
---

# `agrag.agents.result.AgentRunResult` \{#agrag-agents-result-AgentRunResult}

Bases: <code>TypedDict</code>

Result of one agent run.

The deep-agent path also passes through the other keys of the LangGraph
state at runtime; only the keys below are part of the contract.

**Attributes:**

- [**messages**](#agrag-agents-result-AgentRunResult-messages) (<code>list\[Any\]</code>) – The conversation, ending with the assistant's answer.
- [**ledger**](#agrag-agents-result-AgentRunResult-ledger) (<code>[Ledger](../ledger/Ledger-ref.md)</code>) – Citation keys assigned during this run. Use
  `ledger.resolve(key)` to get the evidence behind a key.

## `ledger` \{#agrag-agents-result-AgentRunResult-ledger}

```python
ledger: Ledger
```

## `messages` \{#agrag-agents-result-AgentRunResult-messages}

```python
messages: list[Any]
```
