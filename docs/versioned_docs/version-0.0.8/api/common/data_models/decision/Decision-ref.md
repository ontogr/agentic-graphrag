---
title: agrag.common.data_models.decision.Decision
sidebar_label: Decision
---

# `agrag.common.data_models.decision.Decision` \{#agrag-common-data_models-decision-Decision}

Bases: <code>BaseModel</code>

One recorded decision of a task.

**Attributes:**

- [**id**](#agrag-common-data_models-decision-Decision-id) (<code>UUID</code>) – Identifier derived from the task id, choice key and revision.
- [**task_id**](#agrag-common-data_models-decision-Decision-task_id) (<code>UUID</code>) – The task the decision belongs to.
- [**task_name**](#agrag-common-data_models-decision-Decision-task_name) (<code>str</code>) – The name of that task.
- [**choice_key**](#agrag-common-data_models-decision-Decision-choice_key) (<code>str</code>) – The choice inside the task that this decision settles.
- [**revision**](#agrag-common-data_models-decision-Decision-revision) (<code>int</code>) – 1 for the first decision of a choice, and one more for each
  supersession.
- [**conclusion**](#agrag-common-data_models-decision-Decision-conclusion) (<code>str</code>) – The conclusion. Never changed after recording.
- [**rationale**](#agrag-common-data_models-decision-Decision-rationale) (<code>str</code>) – The stated reasoning.
- [**assumptions**](#agrag-common-data_models-decision-Decision-assumptions) (<code>list\[str\]</code>) – Assumptions the decision relies on.
- [**open_questions**](#agrag-common-data_models-decision-Decision-open_questions) (<code>list\[str\]</code>) – Questions left open.
- [**author**](#agrag-common-data_models-decision-Decision-author) (<code>str</code>) – The agent that recorded the decision.
- [**status**](#agrag-common-data_models-decision-Decision-status) (<code>[DecisionStatus](DecisionStatus.md)</code>) – Lifecycle state.
- [**review_state**](#agrag-common-data_models-decision-Decision-review_state) (<code>[ReviewState](ReviewState.md)</code>) – Whether the supports still hold.
- [**review_reason**](#agrag-common-data_models-decision-Decision-review_reason) (<code>[ReviewReason](ReviewReason.md) | None</code>) – Why the decision needs review, or None.
- [**rejection_reason**](#agrag-common-data_models-decision-Decision-rejection_reason) (<code>str | None</code>) – The reason given when the decision was rejected.
- [**rejected_by**](#agrag-common-data_models-decision-Decision-rejected_by) (<code>str | None</code>) – Who rejected the decision.
- [**created_at**](#agrag-common-data_models-decision-Decision-created_at) (<code>datetime</code>) – When the decision was recorded.
- [**supports**](#agrag-common-data_models-decision-Decision-supports) (<code>list\[[Support](Support.md)\]</code>) – The stored supports, in the order they were given.

## `assumptions` \{#agrag-common-data_models-decision-Decision-assumptions}

```python
assumptions: list[str]
```

## `author` \{#agrag-common-data_models-decision-Decision-author}

```python
author: str
```

## `choice_key` \{#agrag-common-data_models-decision-Decision-choice_key}

```python
choice_key: str
```

## `conclusion` \{#agrag-common-data_models-decision-Decision-conclusion}

```python
conclusion: str
```

## `created_at` \{#agrag-common-data_models-decision-Decision-created_at}

```python
created_at: datetime
```

## `id` \{#agrag-common-data_models-decision-Decision-id}

```python
id: UUID
```

## `model_config` \{#agrag-common-data_models-decision-Decision-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `open_questions` \{#agrag-common-data_models-decision-Decision-open_questions}

```python
open_questions: list[str]
```

## `rationale` \{#agrag-common-data_models-decision-Decision-rationale}

```python
rationale: str
```

## `rejected_by` \{#agrag-common-data_models-decision-Decision-rejected_by}

```python
rejected_by: str | None = None
```

## `rejection_reason` \{#agrag-common-data_models-decision-Decision-rejection_reason}

```python
rejection_reason: str | None = None
```

## `review_reason` \{#agrag-common-data_models-decision-Decision-review_reason}

```python
review_reason: ReviewReason | None = None
```

## `review_state` \{#agrag-common-data_models-decision-Decision-review_state}

```python
review_state: ReviewState
```

## `revision` \{#agrag-common-data_models-decision-Decision-revision}

```python
revision: int
```

## `status` \{#agrag-common-data_models-decision-Decision-status}

```python
status: DecisionStatus
```

## `supports` \{#agrag-common-data_models-decision-Decision-supports}

```python
supports: list[Support] = Field(default_factory=list)
```

## `task_id` \{#agrag-common-data_models-decision-Decision-task_id}

```python
task_id: UUID
```

## `task_name` \{#agrag-common-data_models-decision-Decision-task_name}

```python
task_name: str
```
