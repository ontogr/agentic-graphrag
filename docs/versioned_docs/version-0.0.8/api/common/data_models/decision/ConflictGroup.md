---
title: agrag.common.data_models.decision.ConflictGroup
sidebar_label: ConflictGroup
---

# `agrag.common.data_models.decision.ConflictGroup` \{#agrag-common-data_models-decision-ConflictGroup}

Bases: <code>BaseModel</code>

Active decisions of one choice key that disagree across tasks.

**Attributes:**

- [**choice_key**](#agrag-common-data_models-decision-ConflictGroup-choice_key) (<code>str</code>) – The shared choice key.
- [**decisions**](#agrag-common-data_models-decision-ConflictGroup-decisions) (<code>list\[[Decision](Decision-ref.md)\]</code>) – At most the group cap of active decisions, by task name.
- [**truncated**](#agrag-common-data_models-decision-ConflictGroup-truncated) (<code>bool</code>) – Whether some decisions of the group are not shown.

## `choice_key` \{#agrag-common-data_models-decision-ConflictGroup-choice_key}

```python
choice_key: str
```

## `decisions` \{#agrag-common-data_models-decision-ConflictGroup-decisions}

```python
decisions: list[Decision]
```

## `model_config` \{#agrag-common-data_models-decision-ConflictGroup-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `truncated` \{#agrag-common-data_models-decision-ConflictGroup-truncated}

```python
truncated: bool
```
