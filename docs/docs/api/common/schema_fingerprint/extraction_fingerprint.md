---
title: agrag.common.schema_fingerprint.extraction_fingerprint
sidebar_label: extraction_fingerprint
---

# `agrag.common.schema_fingerprint.extraction_fingerprint` \{#agrag-common-schema_fingerprint-extraction_fingerprint}

```python
extraction_fingerprint(schema:GraphSchema, settings:ExtractionSettings, *, effective_mode:Literal['gliner', 'hybrid', 'llm'], llm_model:str | None, prompt_id:str | None) -> str
```

Return the hash of everything the extractor reads besides structure.

The hash covers the entity, relation and property descriptions, the
`ExtractionSettings` fields except `escalation_budget` and `mode`, and
the effective mode. `escalation_threshold` is hashed only for `hybrid`.
The LLM model name and prompt identity are hashed only when the effective
mode is `hybrid` or `llm`. A new settings field is included until it is
added to the exclude list.

**Parameters:**

- **schema** (<code>[GraphSchema](../data_models/graph_schema/GraphSchema.md)</code>) – The schema whose descriptions the extractor reads.
- **settings** (<code>[ExtractionSettings](../../ingestion/settings/ExtractionSettings.md)</code>) – The extraction settings of the run.
- **effective_mode** (<code>Literal['gliner', 'hybrid', 'llm']</code>) – The mode the run uses after the degrade rule.
- **llm_model** (<code>str | None</code>) – The model name of the LLM slot, or None without an LLM.
- **prompt_id** (<code>str | None</code>) – The prompt identity of the LLM tier, or None without an LLM.

**Returns:**

- <code>str</code> – The first 16 hex characters of the SHA-256 of the canonical data.
