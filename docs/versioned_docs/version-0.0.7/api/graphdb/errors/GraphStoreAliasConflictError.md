---
title: agrag.graphdb.errors.GraphStoreAliasConflictError
sidebar_label: GraphStoreAliasConflictError
---

# `agrag.graphdb.errors.GraphStoreAliasConflictError` \{#agrag-graphdb-errors-GraphStoreAliasConflictError}

```python
GraphStoreAliasConflictError(conflicts:dict[str, str]) -> None
```

Bases: <code>[GraphStoreConstraintViolationError](GraphStoreConstraintViolationError.md)</code>

A merge-key alias a merge tried to claim already names another entity.

Unlike the base class, this is not surfaced by the backend's own
uniqueness constraint -- claiming an already-owned alias is a silent
no-op at the database level (see `upsert_merge_alias_query`) -- so
`apply_merge` detects it itself from the claim's own return rows and
raises this instead. For example, one writer creates a canonical entity
named "Bob" while a concurrent writer separately resolves "Bob" as an
accepted alias of a different canonical entity named "Robert": neither
writer's own node merge_key collides, so recovery must come from here,
not from a constraint violation.

**Attributes:**

- [**conflicts**](#agrag-graphdb-errors-GraphStoreAliasConflictError-conflicts) – Every accepted merge_key this claim found already owned,
  mapped to the entity id that owns it.

## `conflicts` \{#agrag-graphdb-errors-GraphStoreAliasConflictError-conflicts}

```python
conflicts = conflicts
```
