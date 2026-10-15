---
title: agrag.memory.tasks
sidebar_label: tasks
---

# `agrag.memory.tasks` \{#agrag-memory-tasks}

Durable task state with raw events and steps, scoped to one project.

`TaskMemory` writes named tasks, appends raw events and sets steps in the
graph store. Each write runs in one transaction, so event sequence numbers are
gapless under concurrent appends and a failed write leaves no partial state.
The project and the author come from the constructor, never from a method
argument. Nothing here calls a model or an embedder.

**Classes:**

- [**BoundedPayload**](BoundedPayload.md) – An event payload cut to the storage limit.
- [**TaskMemory**](TaskMemory.md) – Durable task state for one project, written on behalf of one agent.

**Functions:**

- [**bound_payload**](bound_payload.md) – Cut an event payload to the storage limit and hash the full text.
- [**build_task_view**](build_task_view.md) – Assemble a resume view from a task's counts and step summaries.

**Attributes:**

- [**EVENT_PAGE_LIMIT**](EVENT_PAGE_LIMIT.md) –
- [**MAX_PAYLOAD_CHARACTERS**](MAX_PAYLOAD_CHARACTERS.md) –
- [**MAX_REQUEST_ID_LENGTH**](MAX_REQUEST_ID_LENGTH.md) –
- [**STEP_VIEW_LIMIT**](STEP_VIEW_LIMIT.md) –
