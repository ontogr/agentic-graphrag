---
title: agrag.agents.tools.search.make_answer_from_graph_structure_tool
sidebar_label: make_answer_from_graph_structure_tool
---

# `agrag.agents.tools.search.make_answer_from_graph_structure_tool` \{#agrag-agents-tools-search-make_answer_from_graph_structure_tool}

```python
make_answer_from_graph_structure_tool(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> Any
```

Build the answer_from_graph_structure tool.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine the tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – The caller's base scope, which the tool can only narrow.

**Returns:**

- <code>Any</code> – A decorated tool function.
