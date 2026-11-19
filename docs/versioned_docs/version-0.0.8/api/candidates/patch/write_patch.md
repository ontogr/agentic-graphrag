---
title: agrag.candidates.patch.write_patch
sidebar_label: write_patch
---

# `agrag.candidates.patch.write_patch` \{#agrag-candidates-patch-write_patch}

```python
write_patch(patch:SchemaPatch, path:Path, *, overwrite:bool = False) -> Path
```

Write the patch as indented JSON, refusing replacement by default.

The file is created or truncated only after opening it in exclusive-create
or write mode. A trailing newline is included.

**Parameters:**

- **patch** (<code>[SchemaPatch](../../common/data_models/candidate_review/SchemaPatch.md)</code>) – Patch to serialize.
- **path** (<code>Path</code>) – Destination file path.
- **overwrite** (<code>bool</code>) – Whether to truncate an existing file.

**Returns:**

- <code>Path</code> – The destination path after a successful write.

**Raises:**

- <code>FileExistsError</code> – If the destination exists and overwrite is false.
- <code>OSError</code> – If the destination cannot be opened or written.
