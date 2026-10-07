---
title: agrag.ingestion.merge.merge_properties
sidebar_label: merge_properties
---

# `agrag.ingestion.merge.merge_properties` \{#agrag-ingestion-merge-merge_properties}

```python
merge_properties(property_sources:list[dict[str, object]], rules:PropertyRules, *, description_settings:Any | None = None, description_client:Any | None = None, tracer:Tracer | None = None) -> tuple[dict[str, object], list[ConflictRecord], list[Any]]
```

Return field-resolved properties and records of every real conflict.

**Parameters:**

- **property_sources** (<code>list\[dict\[str, object\]\]</code>) – One dict per source entity/mention, keyed by field.
- **rules** (<code>[PropertyRules](PropertyRules.md)</code>) – The per-property rule table.
- **description_settings** (<code>Any | None</code>) – LLM settings for description summarization.
- **description_client** (<code>Any | None</code>) – Injected LLM client for tests.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Returns:**

- <code>tuple\[dict\[str, object\], list\[[ConflictRecord](ConflictRecord.md)\], list\[Any\]\]</code> – The resolved properties, conflict records, and optional stage failures.
