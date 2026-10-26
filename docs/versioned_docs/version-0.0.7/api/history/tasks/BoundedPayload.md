---
title: agrag.history.tasks.BoundedPayload
sidebar_label: BoundedPayload
---

# `agrag.history.tasks.BoundedPayload` \{#agrag-history-tasks-BoundedPayload}

Bases: <code>NamedTuple</code>

An event payload cut to the storage limit.

**Attributes:**

- [**payload**](#agrag-history-tasks-BoundedPayload-payload) (<code>str</code>) – The stored text, at most `MAX_PAYLOAD_CHARACTERS` long.
- [**truncated**](#agrag-history-tasks-BoundedPayload-truncated) (<code>bool</code>) – Whether the stored text is shorter than the full text.
- [**payload_sha256**](#agrag-history-tasks-BoundedPayload-payload_sha256) (<code>str</code>) – SHA-256 of the full text, encoded as UTF-8.

## `payload` \{#agrag-history-tasks-BoundedPayload-payload}

```python
payload: str
```

## `payload_sha256` \{#agrag-history-tasks-BoundedPayload-payload_sha256}

```python
payload_sha256: str
```

## `truncated` \{#agrag-history-tasks-BoundedPayload-truncated}

```python
truncated: bool
```
