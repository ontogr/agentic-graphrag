---
title: agrag.chunking.chunker.fingerprint_of
sidebar_label: fingerprint_of
---

# `agrag.chunking.chunker.fingerprint_of` \{#agrag-chunking-chunker-fingerprint_of}

```python
fingerprint_of(value:object) -> str
```

Return a short stable hash of a JSON-safe value.

**Parameters:**

- **value** (<code>object</code>) – Data made of dicts, lists, strings, numbers, booleans and `None`.

**Returns:**

- <code>str</code> – The first 16 hex characters of the SHA-256 of the canonical JSON.
