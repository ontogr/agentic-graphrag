---
title: agrag.memory.retention.RetentionMemory
sidebar_label: RetentionMemory
---

# `agrag.memory.retention.RetentionMemory` \{#agrag-memory-retention-RetentionMemory}

```python
RetentionMemory(store:GraphStore, project_id:str, agent_id:str) -> None
```

Apply retention actions to memory owned by one configured project.

**Functions:**

- [**delete_task**](#agrag-memory-retention-RetentionMemory-delete_task) – Delete a task and its events and steps, and optionally its decisions.
- [**redact_event**](#agrag-memory-retention-RetentionMemory-redact_event) – Replace an event body while keeping its identity and payload hash.

## `delete_task` \{#agrag-memory-retention-RetentionMemory-delete_task}

```python
delete_task(name:str, include_decisions:bool = True, request_id:str | None = None) -> RetentionResult
```

Delete a task and its events and steps, and optionally its decisions.

Decisions in other tasks that cite deleted events or decisions are
directly flagged `needs_review`. Their ids are returned; no
transitive review propagation or queueing is performed here.

## `redact_event` \{#agrag-memory-retention-RetentionMemory-redact_event}

```python
redact_event(event_id:str, request_id:str | None = None) -> RetentionResult
```

Replace an event body while keeping its identity and payload hash.

The event remains in sequence and receives a `redacted_at` timestamp.
A retry with the same request id replays the first result.
