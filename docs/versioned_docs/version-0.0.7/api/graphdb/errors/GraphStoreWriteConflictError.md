---
title: agrag.graphdb.errors.GraphStoreWriteConflictError
sidebar_label: GraphStoreWriteConflictError
---

# `agrag.graphdb.errors.GraphStoreWriteConflictError` \{#agrag-graphdb-errors-GraphStoreWriteConflictError}

Bases: <code>[GraphStoreError](GraphStoreError.md)</code>

A write reached a row that an in-flight job owns and no job can defer it.

Raised inside a transaction when a write without a deferral list finds a
row tagged by another job, so the caller's transaction rolls back instead
of changing a row it does not own.
