---
title: agrag.agents.tools.search
sidebar_label: search
---

# `agrag.agents.tools.search` \{#agrag-agents-tools-search}

Discovery tools: fixed-Recipe searches over SearchEngine.

Each factory returns one LangChain tool bound to an engine, a ledger, and the
caller's base scope. A tool's parameters are exactly the ones it can apply,
and its docstring is the LLM-visible tool description, so it says what the
tool finds and what each argument narrows.

**Functions:**

- [**make_answer_from_graph_structure_tool**](make_answer_from_graph_structure_tool.md) – Build the answer_from_graph_structure tool.
- [**make_answer_thematic_question_tool**](make_answer_thematic_question_tool.md) – Build the answer_thematic_question tool.
- [**make_explore_related_tool**](make_explore_related_tool.md) – Build the explore_related tool.
- [**make_look_up_entity_tool**](make_look_up_entity_tool.md) – Build the look_up_entity tool.
- [**make_query_graph_directly_tool**](make_query_graph_directly_tool.md) – Build the query_graph_directly tool.
- [**make_search_source_text_tool**](make_search_source_text_tool.md) – Build the search_source_text tool.
- [**render_results**](render_results.md) – Render results as cited evidence, or a no-results message.
- [**scoped_filters**](scoped_filters.md) – Narrow the caller's base scope by a tool call's own filter arguments.

**Attributes:**

- [**MAX_TOOL_LIMIT**](MAX_TOOL_LIMIT.md) –
- [**SCOPE_DENIED**](SCOPE_DENIED.md) –
