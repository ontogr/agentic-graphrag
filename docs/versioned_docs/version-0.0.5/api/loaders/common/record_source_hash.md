---
title: agrag.loaders.common.record_source_hash
sidebar_label: record_source_hash
---

# `agrag.loaders.common.record_source_hash` \{#agrag-loaders-common-record_source_hash}

```python
record_source_hash(raw:bytes) -> str
```

Hash the whole raw source bytes for a record-family document.

**Parameters:**

- **raw** (<code>bytes</code>) – The raw source bytes.

**Returns:**

- <code>str</code> – The sha256 hex digest of the bytes.
