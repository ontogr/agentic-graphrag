---
title: agrag.schema.formats.dispatch.read_models
sidebar_label: read_models
---

# `agrag.schema.formats.dispatch.read_models` \{#agrag-schema-formats-dispatch-read_models}

```python
read_models(source:Any) -> GraphSchema
```

Read a schema from a Pydantic class or a list of classes.

The schema is named `custom` and has version `1`. Each warning is
logged. Call `from_pydantic` to set the name and version, or to get the
warnings as a list.
