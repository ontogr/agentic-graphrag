---
title: agrag.common.data_models.task
sidebar_label: task
---

# `agrag.common.data_models.task` \{#agrag-common-data_models-task}

Models for durable task state: tasks, raw events, steps and resume views.

**Classes:**

- [**CreateTaskResult**](CreateTaskResult.md) – The outcome of creating or reusing a task.
- [**Event**](Event.md) – One raw event appended to a task.
- [**EventKind**](EventKind.md) – Kind of a raw event appended to a task.
- [**EventLookup**](EventLookup.md) – The result of reading one event by task and sequence number.
- [**EventPage**](EventPage.md) – One page of events of a task, in sequence order.
- [**MemoryErrorCode**](MemoryErrorCode.md) – Fixed error codes returned by task memory operations.
- [**RecordEventResult**](RecordEventResult.md) – The outcome of appending one event.
- [**SetStepResult**](SetStepResult.md) – The outcome of creating or updating a step.
- [**Step**](Step.md) – A named step of a task with an explicit state.
- [**StepKind**](StepKind.md) – Broad category of a step.
- [**StepPage**](StepPage.md) – One bounded page of steps in a task and state.
- [**StepResultBasis**](StepResultBasis.md) – Whether a step result depends on evidence or stands independently.
- [**StepResultValidity**](StepResultValidity.md) – Whether a completed step result is safe to reuse.
- [**StepState**](StepState.md) – State of a step. Resume reruns every step that is not completed.
- [**StepSummary**](StepSummary.md) – The fields of a step that a resume view shows.
- [**Task**](Task-ref.md) – A named unit of work inside one project.
- [**TaskLookup**](TaskLookup.md) – The result of reading a task view by name.
- [**TaskStatus**](TaskStatus.md) – Lifecycle state of a task.
- [**TaskView**](TaskView.md) – A bounded resume view of one task. It never includes event bodies.
- [**WriteResult**](WriteResult.md) – Base outcome of a task memory write.

**Attributes:**

- [**EVENT_LABEL**](EVENT_LABEL.md) –
- [**HAS_EVENT**](HAS_EVENT.md) –
- [**HAS_STEP**](HAS_STEP.md) –
- [**PROJECT_LABEL**](PROJECT_LABEL.md) –
- [**REQUEST_LABEL**](REQUEST_LABEL.md) –
- [**STEP_LABEL**](STEP_LABEL.md) –
- [**STEP_STATE_ORDER**](STEP_STATE_ORDER.md) (<code>tuple\[[StepState](StepState.md), ...\]</code>) –
- [**TASK_LABEL**](TASK_LABEL.md) –
