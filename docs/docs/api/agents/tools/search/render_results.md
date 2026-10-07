---
title: agrag.agents.tools.search.render_results
sidebar_label: render_results
---

# `agrag.agents.tools.search.render_results` \{#agrag-agents-tools-search-render_results}

```python
render_results(ledger:'Ledger', results:list[Any]) -> str
```

Render results as cited evidence, or a no-results message.

**Parameters:**

- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **results** (<code>list\[Any\]</code>) – The results to render.

**Returns:**

- <code>str</code> – One cited line per result, or a no-results message when empty.
