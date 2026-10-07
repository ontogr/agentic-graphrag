---
title: agrag.eval.run_resolver_detailed
sidebar_label: run_resolver_detailed
---

# `agrag.eval.run_resolver_detailed` \{#agrag-eval-run_resolver_detailed}

```python
run_resolver_detailed(resolver:Resolver, mentions:Sequence[str], *, label:str = 'Organization') -> tuple[ClusterAssignment, ResolutionResult]
```

Resolve mention strings and return the clusters plus raw evidence.

Each mention becomes one entity in its own chunk. The chunk holds only the
mention text, and is registered with any `LLMVerify` comparator of the
resolver so the comparator can look it up. Chunk ids come from the mention
position, so runs are repeatable.

**Parameters:**

- **resolver** (<code>[Resolver](../ingestion/resolve/resolver/Resolver-ref.md)</code>) – The resolver under test.
- **mentions** (<code>Sequence\[str\]</code>) – The mention texts.
- **label** (<code>str</code>) – The entity label given to every mention.

**Returns:**

- <code>[ClusterAssignment](resolution/ClusterAssignment.md)</code> – The predicted clusters with the counts of matches per comparator and
- <code>[ResolutionResult](../ingestion/resolve/resolver/ResolutionResult.md)</code> – of failed LLM requests, and the raw `ResolutionResult` whose match
- <code>tuple\[[ClusterAssignment](resolution/ClusterAssignment.md), [ResolutionResult](../ingestion/resolve/resolver/ResolutionResult.md)\]</code> – records carry the comparator that confirmed each pair.
