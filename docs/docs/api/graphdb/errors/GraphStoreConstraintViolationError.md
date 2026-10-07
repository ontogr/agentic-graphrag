---
title: agrag.graphdb.errors.GraphStoreConstraintViolationError
sidebar_label: GraphStoreConstraintViolationError
---

# `agrag.graphdb.errors.GraphStoreConstraintViolationError` \{#agrag-graphdb-errors-GraphStoreConstraintViolationError}

Bases: <code>[GraphStoreError](GraphStoreError.md)</code>

A write violated a uniqueness constraint the backend enforces.

Raised instead of letting the backend's own driver exception propagate,
so callers can recognize this specific case -- for example, two
concurrent writers both missing an exact-match lookup and racing to
create the same `merge_key` -- and recover by re-resolving to
whichever write landed first, rather than treating it as a fatal error.
