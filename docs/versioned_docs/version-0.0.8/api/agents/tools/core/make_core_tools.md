---
title: agrag.agents.tools.core.make_core_tools
sidebar_label: make_core_tools
---

# `agrag.agents.tools.core.make_core_tools` \{#agrag-agents-tools-core-make_core_tools}

```python
make_core_tools(*, graph_store:GraphStore, embedder:Embedder, scope:frozenset[str], task_name:str, history:ConversationHistory, decisions:DecisionTraces, fetched_ids:list[str], fetched_outcomes:Sequence[FetchOutcome], max_chars:int, max_tool_calls:int, retrieval_settings:RetrievalSettings, reranker:Reranker | None = None, timeout:float | None = None, vector_store:VectorStore | None = None) -> tuple[list[Any], RunState]
```

Bind evidence, history, and decision tools to one trusted task scope.
