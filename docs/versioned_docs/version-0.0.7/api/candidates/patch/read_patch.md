---
title: agrag.candidates.patch.read_patch
sidebar_label: read_patch
---

# `agrag.candidates.patch.read_patch` \{#agrag-candidates-patch-read_patch}

```python
read_patch(path:Path) -> SchemaPatch
```

Read a JSON file and validate it as a schema patch.

**Parameters:**

- **path** (<code>Path</code>) – Patch file to read.

**Returns:**

- <code>[SchemaPatch](../../common/data_models/candidate_review/SchemaPatch.md)</code> – Validated schema patch.

**Raises:**

- <code>OSError</code> – If the file cannot be read.
- <code>ValueError</code> – If its contents are invalid JSON or do not match the model.
