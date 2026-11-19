---
title: agrag.common.fingerprint.fingerprint_of
sidebar_label: fingerprint_of
---

# `agrag.common.fingerprint.fingerprint_of` \{#agrag-common-fingerprint-fingerprint_of}

```python
fingerprint_of(value:object) -> str
```

Return a short stable hash of a JSON-safe value.

**Parameters:**

- **value** (<code>object</code>) – Data made of dicts, lists, strings, numbers, booleans and `None`.

**Returns:**

- <code>str</code> – The first 16 hex characters of the SHA-256 of the canonical JSON. Keys
- <code>str</code> – are sorted at every depth, so key order never changes the result. List
- <code>str</code> – order does.
