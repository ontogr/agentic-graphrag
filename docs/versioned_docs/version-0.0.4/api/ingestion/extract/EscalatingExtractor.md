---
title: agrag.ingestion.extract.EscalatingExtractor
sidebar_label: EscalatingExtractor
---

# `agrag.ingestion.extract.EscalatingExtractor` \{#agrag-ingestion-extract-EscalatingExtractor}

```python
EscalatingExtractor(primary:Extractor, escalate_to:Extractor, *, min_confidence:float = 0.5, min_chunk_words:int = 8, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](Extractor.md)</code>

Runs a cheap primary extractor first, escalating per chunk when it's weak.

**Functions:**

- [**extract**](#agrag-ingestion-extract-EscalatingExtractor-extract) – Extract with the primary extractor, escalating when it's weak.

**Attributes:**

- [**escalate_to**](#agrag-ingestion-extract-EscalatingExtractor-escalate_to) –
- [**min_chunk_words**](#agrag-ingestion-extract-EscalatingExtractor-min_chunk_words) –
- [**min_confidence**](#agrag-ingestion-extract-EscalatingExtractor-min_confidence) –
- [**primary**](#agrag-ingestion-extract-EscalatingExtractor-primary) –

**Parameters:**

- **primary** (<code>[Extractor](Extractor.md)</code>) – Runs first, for every chunk.
- **escalate_to** (<code>[Extractor](Extractor.md)</code>) – Runs instead of, never in addition to, the primary's
  result, when escalation triggers. Merging both extractors'
  output would mean reconciling overlapping spans between them,
  which is what entity resolution is for, not extraction.
- **min_confidence** (<code>float</code>) – Escalate when the primary's mean entity confidence
  falls below this, among entities that report a confidence.
- **min_chunk_words** (<code>int</code>) – Below this word count, a zero-entity result from
  the primary is treated as plausibly correct, not a miss.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.extraction.escalating` span. `None`
  opens no recorded span.

## `escalate_to` \{#agrag-ingestion-extract-EscalatingExtractor-escalate_to}

```python
escalate_to = escalate_to
```

## `extract` \{#agrag-ingestion-extract-EscalatingExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the primary extractor, escalating when it's weak.

Returns escalate_to's result outright when escalation triggers, never
a combination of both extractors' results.

## `min_chunk_words` \{#agrag-ingestion-extract-EscalatingExtractor-min_chunk_words}

```python
min_chunk_words = min_chunk_words
```

## `min_confidence` \{#agrag-ingestion-extract-EscalatingExtractor-min_confidence}

```python
min_confidence = min_confidence
```

## `primary` \{#agrag-ingestion-extract-EscalatingExtractor-primary}

```python
primary = primary
```
