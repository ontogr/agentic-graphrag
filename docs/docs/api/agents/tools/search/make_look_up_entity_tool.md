---
title: agrag.agents.tools.search.make_look_up_entity_tool
sidebar_label: make_look_up_entity_tool
---

# `agrag.agents.tools.search.make_look_up_entity_tool` \{#agrag-agents-tools-search-make_look_up_entity_tool}

```python
make_look_up_entity_tool(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> Any
```

Build the look_up_entity tool.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine the tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – The caller's base scope, which the tool can only narrow.

**Returns:**

- <code>Any</code> – A decorated tool function.
