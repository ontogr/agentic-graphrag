---
title: agrag.agents.tools.traversal.make_list_relationship_types_tool
sidebar_label: make_list_relationship_types_tool
---

# `agrag.agents.tools.traversal.make_list_relationship_types_tool` \{#agrag-agents-tools-traversal-make_list_relationship_types_tool}

```python
make_list_relationship_types_tool(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> Any
```

Build the list_relationship_types tool.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine the tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – The caller's base scope, which the tool cannot widen.

**Returns:**

- <code>Any</code> – A decorated tool function.
