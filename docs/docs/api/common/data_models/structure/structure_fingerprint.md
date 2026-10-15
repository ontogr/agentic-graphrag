---
title: agrag.common.data_models.structure.structure_fingerprint
sidebar_label: structure_fingerprint
---

# `agrag.common.data_models.structure.structure_fingerprint` \{#agrag-common-data_models-structure-structure_fingerprint}

```python
structure_fingerprint(document:Document) -> str
```

Return a sha256 hex digest of the section tree of a document.

The digest covers each section's heading, depth and parent, and each unit's
kind and character span. It does not cover the text, which the content hash
covers. The same text split into different sections gives different digests.

**Parameters:**

- **document** (<code>[Document](../document/Document-ref.md)</code>) – The document.

**Returns:**

- <code>str</code> – The digest, or the empty string when the document has no sections.
