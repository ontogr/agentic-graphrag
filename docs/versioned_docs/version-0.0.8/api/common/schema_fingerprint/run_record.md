---
title: agrag.common.schema_fingerprint.run_record
sidebar_label: run_record
---

# `agrag.common.schema_fingerprint.run_record` \{#agrag-common-schema_fingerprint-run_record}

```python
run_record(schema:GraphSchema, settings:ExtractionSettings, *, effective_mode:Literal['gliner', 'hybrid', 'llm'], llm_model:str | None, prompt_id:str | None, llm_output:LLMOutputSettings | None = None) -> RunRecord
```

Build the run record of a schema and a set of extraction settings.

**Parameters:**

- **schema** (<code>[GraphSchema](../data_models/graph_schema/GraphSchema.md)</code>) – The schema of the run.
- **settings** (<code>[ExtractionSettings](../../ingestion/settings/ExtractionSettings.md)</code>) – The extraction settings of the run.
- **effective_mode** (<code>Literal['gliner', 'hybrid', 'llm']</code>) – The mode the run uses after the degrade rule.
- **llm_model** (<code>str | None</code>) – The model name of the LLM slot, or None without an LLM.
- **prompt_id** (<code>str | None</code>) – The prompt identity of the LLM tier, or None without an LLM.
- **llm_output** (<code>[LLMOutputSettings](LLMOutputSettings.md) | None</code>) – The output options of the LLM slot, or None when the slot
  has none to report.

**Returns:**

- <code>[RunRecord](RunRecord.md)</code> – The record with name, version and both fingerprints.
