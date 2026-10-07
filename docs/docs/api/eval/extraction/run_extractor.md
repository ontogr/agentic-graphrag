---
title: agrag.eval.extraction.run_extractor
sidebar_label: run_extractor
---

# `agrag.eval.extraction.run_extractor` \{#agrag-eval-extraction-run_extractor}

```python
run_extractor(extractor:Extractor, items:Sequence[ExtractionGold], schema:GraphSchema, *, concurrency:int = _CONCURRENCY) -> list[LLMTestCase]
```

Run an extractor over gold items and build one test case per item.

Chunk and document ids come from the item id, so runs are repeatable.

**Parameters:**

- **extractor** (<code>[Extractor](../../ingestion/extract/Extractor.md)</code>) – The extractor under test.
- **items** (<code>Sequence\[[ExtractionGold](ExtractionGold.md)\]</code>) – The gold-annotated chunks.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema the extractor works to.
- **concurrency** (<code>int</code>) – The most extractor calls that run at once. Lower it for an
  endpoint that limits concurrent requests.

**Returns:**

- <code>list\[LLMTestCase\]</code> – One test case per item, in the order of `items`.

**Raises:**

- <code>ValueError</code> – `concurrency` is less than 1.
