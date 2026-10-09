---
title: agrag.common.data_models.provenance.PageProvenance
sidebar_label: PageProvenance
---

# `agrag.common.data_models.provenance.PageProvenance` \{#agrag-common-data_models-provenance-PageProvenance}

Bases: <code>BaseModel</code>

The location of a chunk across one or more pages.

A chunk can start on one page and end on the next page. Each entry in `page_spans`
covers one page.

**Attributes:**

- [**kind**](#agrag-common-data_models-provenance-PageProvenance-kind) (<code>Literal['page']</code>) – The literal tag `"page"`. Marks this as page provenance.
- [**page_spans**](#agrag-common-data_models-provenance-PageProvenance-page_spans) (<code>list\[[PageSpan](PageSpan.md)\]</code>) – The page spans for this chunk. Has more than one entry when
  the chunk crosses a page boundary.

## `kind` \{#agrag-common-data_models-provenance-PageProvenance-kind}

```python
kind: Literal['page'] = 'page'
```

## `page_spans` \{#agrag-common-data_models-provenance-PageProvenance-page_spans}

```python
page_spans: list[PageSpan]
```
