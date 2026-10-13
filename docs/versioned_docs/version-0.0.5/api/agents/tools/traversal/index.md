---
title: agrag.agents.tools.traversal
sidebar_label: traversal
---

# `agrag.agents.tools.traversal` \{#agrag-agents-tools-traversal}

Entity-graph tools: resolve a named entity, then walk its relationships.

Each factory returns one LangChain tool bound to an engine, a ledger, and the
caller's base scope. Every tool here resolves its `entity` argument through
`SearchEngine.find_entity` exactly once before doing anything else, so a name
the caller's scope does not cover stops at "Entity not found." instead of
being traversed anyway.

**Functions:**

- [**make_describe_entity_tool**](make_describe_entity_tool.md) – Build the describe_entity tool.
- [**make_find_related_entities_tool**](make_find_related_entities_tool.md) – Build the find_related_entities tool.
- [**make_list_relationship_types_tool**](make_list_relationship_types_tool.md) – Build the list_relationship_types tool.
- [**make_traverse_from_entity_tool**](make_traverse_from_entity_tool.md) – Build the traverse_from_entity tool.
