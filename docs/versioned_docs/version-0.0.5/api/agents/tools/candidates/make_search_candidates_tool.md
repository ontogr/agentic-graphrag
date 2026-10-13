---
title: agrag.agents.tools.candidates.make_search_candidates_tool
sidebar_label: make_search_candidates_tool
---

# `agrag.agents.tools.candidates.make_search_candidates_tool` \{#agrag-agents-tools-candidates-make_search_candidates_tool}

```python
make_search_candidates_tool(engine:SearchEngine) -> Any
```

Build the search_unreviewed_candidates tool.

**Parameters:**

- **engine** (<code>[SearchEngine](../../../retrieval/search_engine/SearchEngine.md)</code>) – The SearchEngine the tool calls.

**Returns:**

- <code>Any</code> – A decorated tool function.
