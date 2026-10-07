---
title: agrag.retrieval.methods.traversal
sidebar_label: traversal
---

# `agrag.retrieval.methods.traversal` \{#agrag-retrieval-methods-traversal}

Entity resolution and seeded traversal, callable without a SearchEngine.

Free functions, not methods, for the same reason `vector.py`'s
`vector_search` is: the retrieval building blocks stay independently
testable and `SearchEngine` stays an orchestrator over them.

**Functions:**

- [**extract_entity_ids**](extract_entity_ids.md) – Return raw entity ids from results, preserving order.
- [**find_entity**](find_entity.md) – Resolve a named entity to its top search hit, or None.
- [**list_relationship_types**](list_relationship_types.md) – List the relationship types directly attached to a resolved entity.
- [**traverse**](traverse.md) – Expand one resolved entity into its neighbours.

**Attributes:**

- [**logger**](../../retrievers/text2cypher/logger.md) –
