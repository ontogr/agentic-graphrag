---
title: agrag.memory.tasks.build_task_view
sidebar_label: build_task_view
---

# `agrag.memory.tasks.build_task_view` \{#agrag-memory-tasks-build_task_view}

```python
build_task_view(*, task_name:str, goal:str, status:TaskStatus, last_event_seq:int, step_counts:Mapping[StepState, int], steps:Sequence[StepSummary], decisions:Sequence[Decision] = (), decision_count:int | None = None, review_decisions:Sequence[Decision] = (), conflicts:Sequence[ConflictGroup] = (), conflicts_truncated:bool = False) -> TaskView
```

Assemble a resume view from a task's counts and step summaries.

The steps are sorted by `STEP_STATE_ORDER` and then by name, and the
first `STEP_VIEW_LIMIT` of them are shown. Counts come from the caller
and include steps that are not shown.

**Parameters:**

- **task_name** (<code>str</code>) – The task name.
- **goal** (<code>str</code>) – The task goal.
- **status** (<code>[TaskStatus](../../common/data_models/task/TaskStatus.md)</code>) – The task status.
- **last_event_seq** (<code>int</code>) – The sequence number of the last event, or 0.
- **step_counts** (<code>Mapping\[[StepState](../../common/data_models/task/StepState.md), int\]</code>) – The number of steps in each state. Missing states count
  as zero.
- **steps** (<code>Sequence\[[StepSummary](../../common/data_models/task/StepSummary.md)\]</code>) – Step summaries to choose from. The list may be longer than the
  cap, or cover only part of the task.
- **decisions** (<code>Sequence\[[Decision](../../common/data_models/decision/Decision-ref.md)\]</code>) – Active decisions to include in the bounded resume view.
- **decision_count** (<code>int | None</code>) – Total active decisions before applying the view cap.
- **review_decisions** (<code>Sequence\[[Decision](../../common/data_models/decision/Decision-ref.md)\]</code>) – Active decisions that need review.
- **conflicts** (<code>Sequence\[[ConflictGroup](../../common/data_models/decision/ConflictGroup.md)\]</code>) – Cross-task conflicts touching this task.
- **conflicts_truncated** (<code>bool</code>) – Whether more than ten conflicts match.

**Returns:**

- <code>[TaskView](../../common/data_models/task/TaskView.md)</code> – The view. `steps_truncated` is true when the counts exceed the
- <code>[TaskView](../../common/data_models/task/TaskView.md)</code> – number of shown steps.
