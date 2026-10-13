---
title: agrag.agents.tools.traversal.make_find_related_entities_tool
sidebar_label: make_find_related_entities_tool
---

# `agrag.agents.tools.traversal.make_find_related_entities_tool` \{#agrag-agents-tools-traversal-make_find_related_entities_tool}

```python
make_find_related_entities_tool(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> Any
```

Build the find_related_entities tool.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine the tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – The caller's base scope, which the tool cannot widen and
  which also bounds the traversal, so a resolved entity cannot
  reach neighbours outside its caller's scope.

**Returns:**

- <code>Any</code> – A decorated tool function.
