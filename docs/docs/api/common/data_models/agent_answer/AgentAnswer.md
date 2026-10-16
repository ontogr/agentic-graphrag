---
title: agrag.common.data_models.agent_answer.AgentAnswer
sidebar_label: AgentAnswer
---

# `agrag.common.data_models.agent_answer.AgentAnswer` \{#agrag-common-data_models-agent_answer-AgentAnswer}

Bases: <code>BaseModel</code>

A final answer with an explicit evidence-support assessment.

**Attributes:**

- [**answer**](#agrag-common-data_models-agent_answer-AgentAnswer-answer) (<code>str</code>) –
- [**citations**](#agrag-common-data_models-agent_answer-AgentAnswer-citations) (<code>list\[str\]</code>) –
- [**model_config**](#agrag-common-data_models-agent_answer-AgentAnswer-model_config) –
- [**support_status**](#agrag-common-data_models-agent_answer-AgentAnswer-support_status) (<code>Literal['supported', 'insufficient_evidence']</code>) –

## `answer` \{#agrag-common-data_models-agent_answer-AgentAnswer-answer}

```python
answer: str
```

## `citations` \{#agrag-common-data_models-agent_answer-AgentAnswer-citations}

```python
citations: list[str] = Field(default_factory=list)
```

## `model_config` \{#agrag-common-data_models-agent_answer-AgentAnswer-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `support_status` \{#agrag-common-data_models-agent_answer-AgentAnswer-support_status}

```python
support_status: Literal['supported', 'insufficient_evidence']
```
