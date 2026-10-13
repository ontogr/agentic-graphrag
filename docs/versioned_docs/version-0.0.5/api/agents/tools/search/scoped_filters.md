---
title: agrag.agents.tools.search.scoped_filters
sidebar_label: scoped_filters
---

# `agrag.agents.tools.search.scoped_filters` \{#agrag-agents-tools-search-scoped_filters}

```python
scoped_filters(base:'SearchFilters | None', *, labels:list[str] | None = None, document_ids:list[str] | None = None) -> 'SearchFilters | None'
```

Narrow the caller's base scope by a tool call's own filter arguments.

The base scope is an authorization boundary the model can neither see
nor override. A tool argument can only narrow it: labels and document
ids are intersected with the base values, and a request whose
intersection is empty raises rather than searching wider than the
caller allowed. Property constraints come from the base scope only and
are carried through unchanged.

**Parameters:**

- **base** (<code>'SearchFilters | None'</code>) – The scope the caller set when building the tools, or None
  when the caller set none.
- **labels** (<code>list\[str\] | None</code>) – Labels this call asked to search, or None when the call
  asked for no label restriction.
- **document_ids** (<code>list\[str\] | None</code>) – Document ids this call asked to search, or None when
  the call asked for no document restriction.

**Returns:**

- <code>'SearchFilters | None'</code> – The filters the search should run with, or None when neither the
- <code>'SearchFilters | None'</code> – base scope nor the call's arguments constrain anything.

**Raises:**

- <code>[ScopeDeniedError](../../../retrieval/errors/ScopeDeniedError.md)</code> – A requested label or document id is not inside
  the base scope.
