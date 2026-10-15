---
title: agrag.evidence.navigate.navigate
sidebar_label: navigate
---

# `agrag.evidence.navigate.navigate` \{#agrag-evidence-navigate-navigate}

```python
navigate(store:GraphStore, evidence_id:str, relation:NavigationRelation, *, scope:frozenset[str], limit:int, max_chars:int) -> NavigationResult
```

Return the passages that one relation reaches from an evidence id.

A span id starts from the chunk of its version that covers the first
character of the span. A chunk id starts from that chunk. Neighbors are read
in the version of the starting chunk, whether or not that version is current.
An id that names no evidence in scope, and a missing id, both give
`unavailable`.

`parent` returns one item for each section that holds the starting passage,
and `multi_section` is True when there is more than one. `siblings`
returns the other sections under the same parent section. `table_context`
returns the row passages before and after a table passage, with the passage
itself. Every table passage repeats the header rows, so no row is returned
without its header.

The text of the items is cut to `max_chars` in total, in the order of the
items. An item cut by the budget is marked `text_truncated`. An item beyond
`limit` is dropped. Either bound sets `truncated` and the reason.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to read.
- **evidence_id** (<code>str</code>) – The evidence id of the starting passage.
- **relation** (<code>[NavigationRelation](../../common/data_models/navigation/NavigationRelation.md)</code>) – The relation to follow.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents the caller may read. An empty scope makes
  every id unavailable.
- **limit** (<code>int</code>) – The most items to return. Must be between 1 and 50.
- **max_chars** (<code>int</code>) – The most characters of item text to return. Must be between 1
  and 20000.

**Returns:**

- <code>[NavigationResult](../../common/data_models/navigation/NavigationResult.md)</code> – The items, the status and the truncation information.

**Raises:**

- <code>ValueError</code> – `limit` or `max_chars` is outside its range.
