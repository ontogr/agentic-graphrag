---
title: agrag.memory.tasks.bound_payload
sidebar_label: bound_payload
---

# `agrag.memory.tasks.bound_payload` \{#agrag-memory-tasks-bound_payload}

```python
bound_payload(text:str) -> BoundedPayload
```

Cut an event payload to the storage limit and hash the full text.

**Parameters:**

- **text** (<code>str</code>) – The full payload.

**Returns:**

- <code>[BoundedPayload](BoundedPayload.md)</code> – The stored text, whether it was cut, and the hash of the full text.
