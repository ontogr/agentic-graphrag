---
title: agrag.loaders.common.text_sections
sidebar_label: text_sections
---

# `agrag.loaders.common.text_sections` \{#agrag-loaders-common-text_sections}

```python
text_sections(text:str) -> list[DocumentSection]
```

Return one section with an empty heading that holds the text as paragraphs.

**Parameters:**

- **text** (<code>str</code>) – The document text.

**Returns:**

- <code>list\[[DocumentSection](../../common/data_models/document/DocumentSection.md)\]</code> – A list with one section, or an empty list when the text is blank.
