---
title: agrag.graphdb.errors.GraphStoreDataIntegrityError
sidebar_label: GraphStoreDataIntegrityError
---

# `agrag.graphdb.errors.GraphStoreDataIntegrityError` \{#agrag-graphdb-errors-GraphStoreDataIntegrityError}

Bases: <code>[GraphStoreError](GraphStoreError.md)</code>

A read found the graph store in a state its own invariants forbid.

Raised when persisted data cannot be trusted at face value -- for
example a `merged_into` tombstone chain that cycles, points at a
missing node, or runs past its expected bound without reaching a live
node. Returning the last-seen data in these cases would let a caller
silently act on a tombstone instead of the entity it was absorbed into.
