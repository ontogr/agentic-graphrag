---
title: agrag.eval.resolution.run_resolver
sidebar_label: run_resolver
---

# `agrag.eval.resolution.run_resolver` \{#agrag-eval-resolution-run_resolver}

```python
run_resolver(resolver:Resolver, mentions:Sequence[str], *, label:str = 'Organization') -> ClusterAssignment
```

Resolve mention strings and return the clusters the resolver forms.

See `run_resolver_detailed` for the chunk construction. Use that variant
when a caller also needs the raw `ResolutionResult` evidence.

**Parameters:**

- **resolver** (<code>[Resolver](../../ingestion/resolve/resolver/Resolver-ref.md)</code>) – The resolver under test.
- **mentions** (<code>Sequence\[str\]</code>) – The mention texts.
- **label** (<code>str</code>) – The entity label given to every mention.

**Returns:**

- <code>[ClusterAssignment](ClusterAssignment.md)</code> – The predicted clusters, the count of matches per comparator, and
- <code>[ClusterAssignment](ClusterAssignment.md)</code> – the count of failed LLM requests.
