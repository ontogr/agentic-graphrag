---
title: agrag.memory.tasks.BoundedPayload
sidebar_label: BoundedPayload
---

# `agrag.memory.tasks.BoundedPayload` \{#agrag-memory-tasks-BoundedPayload}

Bases: <code>NamedTuple</code>

An event payload cut to the storage limit.

**Attributes:**

- [**payload**](#agrag-memory-tasks-BoundedPayload-payload) (<code>str</code>) – The stored text, at most `MAX_PAYLOAD_CHARACTERS` long.
- [**truncated**](#agrag-memory-tasks-BoundedPayload-truncated) (<code>bool</code>) – Whether the stored text is shorter than the full text.
- [**payload_sha256**](#agrag-memory-tasks-BoundedPayload-payload_sha256) (<code>str</code>) – SHA-256 of the full text, encoded as UTF-8.

## `payload` \{#agrag-memory-tasks-BoundedPayload-payload}

```python
payload: str
```

## `payload_sha256` \{#agrag-memory-tasks-BoundedPayload-payload_sha256}

```python
payload_sha256: str
```

## `truncated` \{#agrag-memory-tasks-BoundedPayload-truncated}

```python
truncated: bool
```
