---
title: agrag.graphdb.cypher_store.require_deferred
sidebar_label: require_deferred
---

# `agrag.graphdb.cypher_store.require_deferred` \{#agrag-graphdb-cypher_store-require_deferred}

```python
require_deferred(pending_job_id:UUID | None, deferred:DeferredWrites | None) -> None
```

Reject a job write that has nowhere to put deferred writes.
