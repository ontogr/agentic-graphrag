---
title: agrag.agents.tools.make_tools
sidebar_label: make_tools
---

# `agrag.agents.tools.make_tools` \{#agrag-agents-tools-make_tools}

```python
make_tools(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> list[Any]
```

Build the agent's tool set over one SearchEngine and Ledger.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine every tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – Caller-set retrieval scope applied to every tool's
  search, e.g. document or tenant constraints. The model never
  sees this scope and cannot widen it: a tool argument that
  falls outside it is refused rather than merged. None searches
  unscoped.

**Returns:**

- <code>list\[Any\]</code> – A list of LangChain tool instances: search_source_text,
- <code>list\[Any\]</code> – look_up_entity, explore_related, answer_from_graph_structure,
- <code>list\[Any\]</code> – answer_thematic_question, list_relationship_types,
- <code>list\[Any\]</code> – find_related_entities, describe_entity, traverse_from_entity,
- <code>list\[Any\]</code> – and compute_over_evidence. query_graph_directly joins them
- <code>list\[Any\]</code> – only when filters is None or empty: it runs a generated
- <code>list\[Any\]</code> – read-only Cypher query, which cannot be confined to a caller
- <code>list\[Any\]</code> – scope, so a scoped agent never receives it.
