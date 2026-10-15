---
title: agrag.memory.tasks.TaskMemory
sidebar_label: TaskMemory
---

# `agrag.memory.tasks.TaskMemory` \{#agrag-memory-tasks-TaskMemory}

```python
TaskMemory(store:GraphStore, *, project_id:str, agent_id:str) -> None
```

Durable task state for one project, written on behalf of one agent.

Operations take the project and author from this constructor. Each write
takes an optional `request_id`. A repeated write with the same id and
arguments returns the stored result, and the same id with other arguments
returns `request_id_reused`.

**Functions:**

- [**create_task**](#agrag-memory-tasks-TaskMemory-create_task) – Create a task, or return the existing task of that name.
- [**get_task**](#agrag-memory-tasks-TaskMemory-get_task) – Read the bounded resume view of a task.
- [**list_events**](#agrag-memory-tasks-TaskMemory-list_events) – Read events of a task in sequence order, one page at a time.
- [**record_event**](#agrag-memory-tasks-TaskMemory-record_event) – Append one raw event to a task.
- [**set_step**](#agrag-memory-tasks-TaskMemory-set_step) – Create or update a step of a task.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store that holds the task memory.
- **project_id** (<code>str</code>) – The project every operation is scoped to. Use a value
  from trusted configuration.
- **agent_id** (<code>str</code>) – The author recorded on tasks and events.

## `create_task` \{#agrag-memory-tasks-TaskMemory-create_task}

```python
create_task(name:str, goal:str, *, request_id:str | None = None) -> CreateTaskResult
```

Create a task, or return the existing task of that name.

**Parameters:**

- **name** (<code>str</code>) – The task name, unique within the project.
- **goal** (<code>str</code>) – The goal. An existing task of the same name must have the
  same goal.
- **request_id** (<code>str | None</code>) – Optional id of at most 64 characters for a safe retry.

**Returns:**

- <code>[CreateTaskResult](../../common/data_models/task/CreateTaskResult.md)</code> – The task when recorded. Otherwise `task_exists` when the name is
- <code>[CreateTaskResult](../../common/data_models/task/CreateTaskResult.md)</code> – taken by a task with another goal.

## `get_task` \{#agrag-memory-tasks-TaskMemory-get_task}

```python
get_task(name:str) -> TaskLookup
```

Read the bounded resume view of a task.

The view has the goal, status, last event sequence number and the first
steps in view order, with counts for every state. It has no event
bodies.

**Parameters:**

- **name** (<code>str</code>) – The task name.

**Returns:**

- <code>[TaskLookup](../../common/data_models/task/TaskLookup.md)</code> – The view when the task exists in this project. Otherwise
- <code>[TaskLookup](../../common/data_models/task/TaskLookup.md)</code> – `found` is false.

## `list_events` \{#agrag-memory-tasks-TaskMemory-list_events}

```python
list_events(task_name:str, *, after_seq:int = 0, limit:int = 50) -> EventPage
```

Read events of a task in sequence order, one page at a time.

**Parameters:**

- **task_name** (<code>str</code>) – The task name.
- **after_seq** (<code>int</code>) – Return events with a larger sequence number than this.
- **limit** (<code>int</code>) – Maximum events in the page, between 1 and 200.

**Returns:**

- <code>[EventPage](../../common/data_models/task/EventPage.md)</code> – The page. When the task does not exist, `found` is false and the
- <code>[EventPage](../../common/data_models/task/EventPage.md)</code> – page is empty.

## `record_event` \{#agrag-memory-tasks-TaskMemory-record_event}

```python
record_event(task_name:str, kind:EventKind, *, role:str | None = None, name:str | None = None, payload:str, request_id:str | None = None) -> RecordEventResult
```

Append one raw event to a task.

The payload is cut to `MAX_PAYLOAD_CHARACTERS` when longer, and the
event records the hash of the full text. No model is called.

**Parameters:**

- **task_name** (<code>str</code>) – The task the event belongs to.
- **kind** (<code>[EventKind](../../common/data_models/task/EventKind.md)</code>) – The kind of event.
- **role** (<code>str | None</code>) – The speaker role for a message, or None.
- **name** (<code>str | None</code>) – The tool or source name for a tool event, or None.
- **payload** (<code>str</code>) – The event text.
- **request_id** (<code>str | None</code>) – Optional id of at most 64 characters for a safe retry.

**Returns:**

- <code>[RecordEventResult](../../common/data_models/task/RecordEventResult.md)</code> – The event when recorded. Otherwise `task_not_found`.

## `set_step` \{#agrag-memory-tasks-TaskMemory-set_step}

```python
set_step(task_name:str, name:str, state:StepState, *, kind:StepKind = StepKind.OTHER, result_event_seq:int | None = None, request_id:str | None = None) -> SetStepResult
```

Create or update a step of a task.

**Parameters:**

- **task_name** (<code>str</code>) – The task the step belongs to.
- **name** (<code>str</code>) – The step name, unique within the task.
- **state** (<code>[StepState](../../common/data_models/task/StepState.md)</code>) – The new state. Use `unknown` when the outcome is not known.
- **kind** (<code>[StepKind](../../common/data_models/task/StepKind.md)</code>) – The broad category of the step.
- **result_event_seq** (<code>int | None</code>) – The sequence number of the event that holds the
  result, or None.
- **request_id** (<code>str | None</code>) – Optional id of at most 64 characters for a safe retry.

**Returns:**

- <code>[SetStepResult](../../common/data_models/task/SetStepResult.md)</code> – The step when recorded. Otherwise `task_not_found` or
- <code>[SetStepResult](../../common/data_models/task/SetStepResult.md)</code> – `event_not_found` when `result_event_seq` names no event.
