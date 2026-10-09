---
title: agrag.loaders.common.read_within_limit
sidebar_label: read_within_limit
---

# `agrag.loaders.common.read_within_limit` \{#agrag-loaders-common-read_within_limit}

```python
read_within_limit(stream:BinaryIO, source:SourceRef, opts:ReadOptions) -> bytes
```

Read a source's bytes without exceeding `max_document_bytes`.

Rejects a source whose known size already exceeds the limit before reading, and
caps the actual read one byte past the limit so a source with no reported size
cannot be buffered past the configured bound either.

**Parameters:**

- **stream** (<code>BinaryIO</code>) – The open binary stream for the source.
- **source** (<code>[SourceRef](../types/SourceRef.md)</code>) – The source being read.
- **opts** (<code>[ReadOptions](../types/ReadOptions.md)</code>) – The read options, for `max_document_bytes`.

**Returns:**

- <code>bytes</code> – The source's raw bytes.

**Raises:**

- <code>[DocumentTooLargeError](../errors/DocumentTooLargeError.md)</code> – The source is, or would be, over the limit.
- <code>ValueError</code> – `opts.max_document_bytes` is not a positive integer.
