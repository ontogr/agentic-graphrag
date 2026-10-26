---
title: agrag.ingestion.settings.effective_mode
sidebar_label: effective_mode
---

# `agrag.ingestion.settings.effective_mode` \{#agrag-ingestion-settings-effective_mode}

```python
effective_mode(settings:ExtractionSettings, llm_available:bool) -> Literal['gliner', 'hybrid', 'llm']
```

Return the run mode, degrading hybrid to GLiNER when no LLM is available.

**Parameters:**

- **settings** (<code>[ExtractionSettings](ExtractionSettings.md)</code>) – Settings for the run.
- **llm_available** (<code>bool</code>) – Whether an LLM extractor can serve the run.

**Returns:**

- <code>Literal['gliner', 'hybrid', 'llm']</code> – The mode the run uses.
