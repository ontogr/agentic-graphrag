---
title: agrag.history.tasks
sidebar_label: tasks
---

# `agrag.history.tasks` \{#agrag-history-tasks}

Conversation history with raw events and steps, scoped to one project.

`ConversationHistory` writes named tasks, appends raw events and sets steps in
the graph store. Event sequence allocation and event creation share a write
callback. FalkorDB can retain earlier statements when a later statement fails,
so a failed multi-statement write may leave partial state. The project and the
author come from the constructor, never from a method argument. Nothing here
calls a model or an embedder.

**Classes:**

- [**BoundedPayload**](BoundedPayload.md) – An event payload cut to the storage limit.
- [**ConversationHistory**](ConversationHistory.md) – Durable task state for one project, written on behalf of one agent.

**Functions:**

- [**bound_payload**](bound_payload.md) – Cut an event payload to the storage limit and hash the full text.
- [**build_task_view**](build_task_view.md) – Assemble a resume view from a task's counts and step summaries.

**Attributes:**

- [**EVENT_PAGE_LIMIT**](EVENT_PAGE_LIMIT.md) –
- [**MAX_PAYLOAD_CHARACTERS**](MAX_PAYLOAD_CHARACTERS.md) –
- [**MAX_REQUEST_ID_LENGTH**](MAX_REQUEST_ID_LENGTH.md) –
- [**STEP_PAGE_LIMIT**](STEP_PAGE_LIMIT.md) –
- [**STEP_VIEW_LIMIT**](STEP_VIEW_LIMIT.md) –
