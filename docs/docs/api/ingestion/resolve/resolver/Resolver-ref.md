---
title: agrag.ingestion.resolve.resolver.Resolver
sidebar_label: Resolver
---

# `agrag.ingestion.resolve.resolver.Resolver` \{#agrag-ingestion-resolve-resolver-Resolver}

```python
Resolver(*, comparators:list[Comparator], candidate_source:CandidateSource, embedder:Embedder | None = None, hard_merge_threshold:float = HARD_MERGE_THRESHOLD, discard_threshold:float = DISCARD_THRESHOLD, max_llm_pairs:int = MAX_LLM_PAIRS, llm_batch_size:int = 10, tracer:Tracer | None = None) -> None
```

Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

Exact identity groups mentions without evidence. A near-identical
fuzzy score merges on the fast path. Every other pair consults its
embedding cosine similarity: at or above the hard-merge threshold it
merges, below the discard threshold it drops, and inside the band it
needs LLM review, capped per label. Tight ambiguous sub-clusters
merge without spending LLM calls.

**Functions:**

- [**resolve**](#agrag-ingestion-resolve-resolver-Resolver-resolve) – Resolve entity groups and retain each confirmed non-exact match.

**Attributes:**

- [**candidate_source**](#agrag-ingestion-resolve-resolver-Resolver-candidate_source) –
- [**comparators**](#agrag-ingestion-resolve-resolver-Resolver-comparators) –
- [**discard_threshold**](#agrag-ingestion-resolve-resolver-Resolver-discard_threshold) –
- [**embedder**](#agrag-ingestion-resolve-resolver-Resolver-embedder) –
- [**hard_merge_threshold**](#agrag-ingestion-resolve-resolver-Resolver-hard_merge_threshold) –
- [**llm_batch_size**](#agrag-ingestion-resolve-resolver-Resolver-llm_batch_size) –
- [**max_llm_pairs**](#agrag-ingestion-resolve-resolver-Resolver-max_llm_pairs) –

**Parameters:**

- **comparators** (<code>list\[[Comparator](Comparator.md)\]</code>) – The ExactMatch, FuzzyMatch, and LLMVerify tiers,
  each picked out by type. A missing ExactMatch or FuzzyMatch
  falls back to its defaults; without an LLMVerify the LLM
  tier is skipped and boundary pairs never merge.
- **candidate_source** (<code>[CandidateSource](../candidate_source/CandidateSource.md)</code>) – Narrows which pairs get compared at all.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md) | None</code>) – Embeds mention texts for the similarity tier. None
  skips that tier: every fuzzy-uncertain pair counts as
  ambiguous, ranked by its fuzzy score.
- **hard_merge_threshold** (<code>float</code>) – Embedding similarity at or above which
  a pair merges without LLM review.
- **discard_threshold** (<code>float</code>) – Embedding similarity below which a pair
  drops without LLM review.
- **max_llm_pairs** (<code>int</code>) – Maximum ambiguous pairs sent to the LLM per
  label.
- **llm_batch_size** (<code>int</code>) – Pairs per LLM request. Must fit the
  LLMVerify comparator's max_pairs_per_batch.
- **tracer** (<code>Tracer | None</code>) – Opens this resolver's spans.

**Raises:**

- <code>ValueError</code> – llm_batch_size is not positive, or exceeds the
  LLMVerify comparator's max_pairs_per_batch.

## `candidate_source` \{#agrag-ingestion-resolve-resolver-Resolver-candidate_source}

```python
candidate_source = candidate_source
```

## `comparators` \{#agrag-ingestion-resolve-resolver-Resolver-comparators}

```python
comparators = comparators
```

## `discard_threshold` \{#agrag-ingestion-resolve-resolver-Resolver-discard_threshold}

```python
discard_threshold = discard_threshold
```

## `embedder` \{#agrag-ingestion-resolve-resolver-Resolver-embedder}

```python
embedder = embedder
```

## `hard_merge_threshold` \{#agrag-ingestion-resolve-resolver-Resolver-hard_merge_threshold}

```python
hard_merge_threshold = hard_merge_threshold
```

## `llm_batch_size` \{#agrag-ingestion-resolve-resolver-Resolver-llm_batch_size}

```python
llm_batch_size = llm_batch_size
```

## `max_llm_pairs` \{#agrag-ingestion-resolve-resolver-Resolver-max_llm_pairs}

```python
max_llm_pairs = max_llm_pairs
```

## `resolve` \{#agrag-ingestion-resolve-resolver-Resolver-resolve}

```python
resolve(entities:list[ExtractedEntity], *, neighbors_by_index:dict[int, list[str]] | None = None, similarity_by_pair:dict[tuple[int, int], float] | None = None) -> ResolutionResult
```

Resolve entity groups and retain each confirmed non-exact match.

**Parameters:**

- **entities** (<code>list\[[ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)\]</code>) – The entities to resolve. Only entities passed in the
  same call are ever compared against each other — resolving
  against previously-resolved entities from an earlier call is
  not supported by this Resolver.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to that entity's neighboring-
  relationship context for LLM verification, when the caller has
  such a source. Omitted by callers that do not.
- **similarity_by_pair** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Already-known real similarity scores keyed by
  `(min(left, right), max(left, right))`, such as an ANN
  backend's hit score. Never drives zone routing -- that scale
  is not comparable to this Resolver's own cosine similarity --
  but reaches the LLM as decision context, preferred over a
  freshly embedded score, for a pair that lands on the boundary
  anyway. Not mutated.

**Returns:**

- <code>[ResolutionResult](ResolutionResult.md)</code> – Groups for every input index, evidence for every confirmed
- <code>[ResolutionResult](ResolutionResult.md)</code> – non-exact pair, the count of uncertain LLM verdicts, and the
- <code>[ResolutionResult](ResolutionResult.md)</code> – counts of failed LLM requests and cap-truncated pairs.
