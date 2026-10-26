---
title: agrag.eval.extraction.extraction_case
sidebar_label: extraction_case
---

# `agrag.eval.extraction.extraction_case` \{#agrag-eval-extraction-extraction_case}

```python
extraction_case(chunk_text:str, predicted:ExtractionResult, gold:ExtractionResult) -> LLMTestCase
```

Build a test case that holds a predicted and a gold extraction.

**Parameters:**

- **chunk_text** (<code>str</code>) – The text the extractor read.
- **predicted** (<code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code>) – The extractor output.
- **gold** (<code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code>) – The gold annotation.

**Returns:**

- <code>LLMTestCase</code> – A test case with serialized predicted and gold extractions.
