---
title: agrag.graphdb.cypher_store.run_fenced_write
sidebar_label: run_fenced_write
---

# `agrag.graphdb.cypher_store.run_fenced_write` \{#agrag-graphdb-cypher_store-run_fenced_write}

```python
run_fenced_write(run:Callable[[str, Mapping[str, Any]], Awaitable[list[dict[str, Any]]]], query:str, parameters:Mapping[str, Any]) -> list[dict[str, Any]]
```

Run a write, fenced by its Cutover Job when the parameters name one.

A write whose parameters carry a non-null `pending_job_id` runs behind
`fenced_write_query`'s guard. A read of the job in the same unit of work
then decides whether the guard held. The returned rows cannot decide it: a
live job's write can return no rows, and a query that ends in an aggregate
returns a row even when the guard matched nothing. A job that stops being
live never becomes live again under the same id, so a failed read means
the job is lost, whichever way the guard went.

**Parameters:**

- **run** (<code>Callable\\[[str, Mapping\[str, Any\]\], Awaitable\[list\[dict\[str, Any\]\]\]\]</code>) – Runs one statement in the caller's unit of work and returns its
  rows. A Neo4j caller passes its transaction, so the lock that the
  guard takes is held until the read.
- **query** (<code>str</code>) – The write query.
- **parameters** (<code>Mapping\[str, Any\]</code>) – The query parameters.

**Returns:**

- <code>list\[dict\[str, Any\]\]</code> – The rows of the write.

**Raises:**

- <code>[GraphStoreFenceError](../errors/GraphStoreFenceError.md)</code> – The job named by `pending_job_id` is no longer
  pending with a live lease.
