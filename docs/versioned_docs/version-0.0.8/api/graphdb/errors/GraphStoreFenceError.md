---
title: agrag.graphdb.errors.GraphStoreFenceError
sidebar_label: GraphStoreFenceError
---

# `agrag.graphdb.errors.GraphStoreFenceError` \{#agrag-graphdb-errors-GraphStoreFenceError}

Bases: <code>[GraphStoreError](GraphStoreError.md)</code>

A pending write ran for a Cutover Job that no longer holds a live lease.

The job's lease expired and recovery claimed it, rolled it back, or gave
the document to a new job. Any row the write tagged is removed by that
rollback, and the job cannot commit.
