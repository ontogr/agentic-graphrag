---
title: agrag.graphdb.errors
sidebar_label: errors
---

# `agrag.graphdb.errors` \{#agrag-graphdb-errors}

Errors that the graph-store layer raises.

**Classes:**

- [**GraphStoreAliasConflictError**](GraphStoreAliasConflictError.md) – A merge-key alias a merge tried to claim already names another entity.
- [**GraphStoreConstraintViolationError**](GraphStoreConstraintViolationError.md) – A write violated a uniqueness constraint the backend enforces.
- [**GraphStoreError**](GraphStoreError.md) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](GraphStoreMissingExtraError.md) – A graph store exists, but its package extra is not installed.
