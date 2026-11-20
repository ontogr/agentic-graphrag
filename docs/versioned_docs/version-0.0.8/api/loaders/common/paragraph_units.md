---
title: agrag.loaders.common.paragraph_units
sidebar_label: paragraph_units
---

# `agrag.loaders.common.paragraph_units` \{#agrag-loaders-common-paragraph_units}

```python
paragraph_units(text:str, offset:int = 0) -> list[Unit]
```

Split text into paragraph units that point at their place in the document.

A blank line ends a paragraph. Each unit span is trimmed of surrounding whitespace.

**Parameters:**

- **text** (<code>str</code>) – The text to split, with LF line endings.
- **offset** (<code>int</code>) – The offset of `text` in the document text.

**Returns:**

- <code>list\[[Unit](../../common/data_models/document/Unit.md)\]</code> – One unit for each non-blank paragraph, in order.
