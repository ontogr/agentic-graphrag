---
title: agrag.common.data_models.provenance.check_page_spans
sidebar_label: check_page_spans
---

# `agrag.common.data_models.provenance.check_page_spans` \{#agrag-common-data_models-provenance-check_page_spans}

```python
check_page_spans(page_spans:list[PageSpan]) -> None
```

Check that page spans number from 1, have ordered boxes, and are in order.

**Parameters:**

- **page_spans** (<code>list\[[PageSpan](PageSpan.md)\]</code>) – The spans to check, in the order they were read.

**Raises:**

- <code>ValueError</code> – A page number is below 1, a box has x0 > x1 or y0 > y1, or
  the page numbers are out of order.
