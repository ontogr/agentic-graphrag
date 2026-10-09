---
title: agrag.agents.tools.search.make_query_graph_directly_tool
sidebar_label: make_query_graph_directly_tool
---

# `agrag.agents.tools.search.make_query_graph_directly_tool` \{#agrag-agents-tools-search-make_query_graph_directly_tool}

```python
make_query_graph_directly_tool(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> Any
```

Build the query_graph_directly tool.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine the tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – Unused; the tool exists only for unscoped agents, so a
  caller scope means make_tools() leaves it out entirely.

**Returns:**

- <code>Any</code> – A decorated tool function.
