---
title: agrag.common.data_models.decision.ConflictList
sidebar_label: ConflictList
---

# `agrag.common.data_models.decision.ConflictList` \{#agrag-common-data_models-decision-ConflictList}

Bases: <code>BaseModel</code>

Choice keys whose active decisions disagree across tasks.

**Attributes:**

- [**groups**](#agrag-common-data_models-decision-ConflictList-groups) (<code>list\[[ConflictGroup](ConflictGroup.md)\]</code>) – At most the group cap of conflict groups.
- [**truncated**](#agrag-common-data_models-decision-ConflictList-truncated) (<code>bool</code>) – Whether some conflict groups are not shown.

## `groups` \{#agrag-common-data_models-decision-ConflictList-groups}

```python
groups: list[ConflictGroup]
```

## `model_config` \{#agrag-common-data_models-decision-ConflictList-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `truncated` \{#agrag-common-data_models-decision-ConflictList-truncated}

```python
truncated: bool
```
