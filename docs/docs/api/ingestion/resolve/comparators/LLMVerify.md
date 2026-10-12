---
title: agrag.ingestion.resolve.comparators.LLMVerify
sidebar_label: LLMVerify
---

# `agrag.ingestion.resolve.comparators.LLMVerify` \{#agrag-ingestion-resolve-comparators-LLMVerify}

```python
LLMVerify(*, chunks_by_id:dict[UUID, Chunk], settings:ExtractionLLMSettings | None = None, client:object | None = None, max_pairs_per_batch:int = 50, tracer:Tracer | None = None) -> None
```

Bases: <code>[Comparator](../resolver/Comparator.md)</code>

Ask an LLM to verify an ambiguous pair. Last resort.

Returns `UNCERTAIN`, never `NO_MATCH`, for a pair it could not judge: a
failed request, missing LLM settings, or a missing or malformed answer. A
pair it did not judge never merges, and a caller must not treat it as
rejected. A missing package extra is a configuration error, not a judgment
call, and is raised outright (see compare's Raises section).

**Attributes:**

- [**failed_requests**](#agrag-ingestion-resolve-comparators-LLMVerify-failed_requests) (<code>int</code>) – Requests that raised.
- [**unavailable_pairs**](#agrag-ingestion-resolve-comparators-LLMVerify-unavailable_pairs) (<code>int</code>) – Pairs skipped because no LLM settings were found.
- [**unavailable_reason**](#agrag-ingestion-resolve-comparators-LLMVerify-unavailable_reason) (<code>str | None</code>) – Why the settings were missing, or None.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-comparators-LLMVerify-compare) – Return the LLM's verdict for one pair, or UNCERTAIN when it gave none.
- [**compare_batch**](#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch) – Verify ambiguous candidate pairs across bounded LLM requests.
- [**compare_batch_detailed**](#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch_detailed) – Verify pairs and count how many verdicts came back uncertain.
- [**compare_with_evidence**](#agrag-ingestion-resolve-comparators-LLMVerify-compare_with_evidence) – Compare two entities and retain any available decision evidence.

**Parameters:**

- **chunks_by_id** (<code>dict\[UUID, [Chunk](../../../common/data_models/chunk/Chunk-ref.md)\]</code>) – Maps a Chunk id to the Chunk, for prompt context.
- **settings** (<code>[ExtractionLLMSettings](../../extract/ExtractionLLMSettings.md) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`.
  Ignored when `client` is given: an injected client also
  disables `settings.retry`, since a caller building its own
  client is assumed to own its own retry behavior too.
- **client** (<code>object | None</code>) – An already-built BAML client. Tests inject a fake here.
- **max_pairs_per_batch** (<code>int</code>) – Maximum pairs sent to the LLM in one request.
  A large ambiguous population is split into requests of at most
  this size so one oversized request cannot exceed the model's
  context limit and silently fail every pair in the batch.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.resolution.llm_verify` span and the
  LLM call spans below it.

## `chunks_by_id` \{#agrag-ingestion-resolve-comparators-LLMVerify-chunks_by_id}

```python
chunks_by_id = chunks_by_id
```

## `compare` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return the LLM's verdict for one pair, or UNCERTAIN when it gave none.

Runs through compare_batch so the single-pair path shares the
batch validation and fail-safe behavior.

**Raises:**

- <code>[ExtractorMissingExtraError](../../extract/ExtractorMissingExtraError.md)</code> – The `llm` package extra is not
  installed.

## `compare_batch` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch}

```python
compare_batch(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> dict[tuple[int, int], ComparisonResult]
```

Verify ambiguous candidate pairs across bounded LLM requests.

Splits into requests of at most `max_pairs_per_batch` pairs so one
oversized population cannot exceed the model's context limit.
Invalid, missing, and uncertain model responses do not merge entities.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md), [ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)\]\]</code>) – `(left_index, right_index, left, right)` tuples to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

## `compare_batch_detailed` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch_detailed}

```python
compare_batch_detailed(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> tuple[dict[tuple[int, int], ComparisonResult], int]
```

Verify pairs and count how many verdicts came back uncertain.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md), [ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)\]\]</code>) – The candidate pairs to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

**Returns:**

- <code>dict\[tuple\[int, int\], [ComparisonResult](../resolver/ComparisonResult.md)\]</code> – The per-pair results and the count of uncertain verdicts, including
- <code>int</code> – missing and malformed answers. A request that errors or has no
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](../resolver/ComparisonResult.md)\], int\]</code> – settings returns UNCERTAIN for its pairs and increments
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](../resolver/ComparisonResult.md)\], int\]</code> – `failed_requests` or `unavailable_pairs` instead.

## `compare_with_evidence` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

## `failed_requests` \{#agrag-ingestion-resolve-comparators-LLMVerify-failed_requests}

```python
failed_requests: int = 0
```

## `max_pairs_per_batch` \{#agrag-ingestion-resolve-comparators-LLMVerify-max_pairs_per_batch}

```python
max_pairs_per_batch = max_pairs_per_batch
```

## `settings` \{#agrag-ingestion-resolve-comparators-LLMVerify-settings}

```python
settings = settings
```

## `unavailable_pairs` \{#agrag-ingestion-resolve-comparators-LLMVerify-unavailable_pairs}

```python
unavailable_pairs: int = 0
```

## `unavailable_reason` \{#agrag-ingestion-resolve-comparators-LLMVerify-unavailable_reason}

```python
unavailable_reason: str | None = None
```
