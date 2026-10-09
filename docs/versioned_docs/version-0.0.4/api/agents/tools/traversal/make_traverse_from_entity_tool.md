---
title: agrag.agents.tools.traversal.make_traverse_from_entity_tool
sidebar_label: make_traverse_from_entity_tool
---

# `agrag.agents.tools.traversal.make_traverse_from_entity_tool` \{#agrag-agents-tools-traversal-make_traverse_from_entity_tool}

```python
make_traverse_from_entity_tool(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> Any
```

Build the traverse_from_entity tool.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine the tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – The caller's base scope, which the tool cannot widen and
  which also bounds the traversal.

**Returns:**

- <code>Any</code> – A decorated tool function.
