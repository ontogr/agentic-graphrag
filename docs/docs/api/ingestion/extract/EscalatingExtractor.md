---
title: agrag.ingestion.extract.EscalatingExtractor
sidebar_label: EscalatingExtractor
---

# `agrag.ingestion.extract.EscalatingExtractor` \{#agrag-ingestion-extract-EscalatingExtractor}

```python
EscalatingExtractor(primary:Extractor, escalate_to:Extractor, *, min_confidence:float = 0.5, min_chunk_words:int = 8, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](Extractor.md)</code>

Run a cheap extractor on every chunk and a stronger one on weak results.

The primary extractor runs first. A chunk escalates when the primary finds
no entities in a chunk of at least `min_chunk_words` words, or when the
mean entity confidence is below `min_confidence`. An escalated chunk gets
the `escalate_to` result alone. The two results are never combined. A
common pairing is `GlinerExtractor` as primary and `BAMLExtractor` as
fallback.

**Parameters:**

- **primary** (<code>[Extractor](Extractor.md)</code>) – Extractor that runs on every chunk.
- **escalate_to** (<code>[Extractor](Extractor.md)</code>) – Extractor that replaces the primary result when escalation
  triggers.
- **min_confidence** (<code>float</code>) – Escalate when the primary's mean reported confidence is
  below this value.
- **min_chunk_words** (<code>int</code>) – Treat an empty primary result as weak only when the
  chunk has at least this many words.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.extraction.escalating` span. `None` opens
  no recorded span.

The `max_concurrency` of this extractor is the smaller of the two child
limits, so a child that must not run concurrently keeps the wrapper serial.

**Functions:**

- [**extract**](#agrag-ingestion-extract-EscalatingExtractor-extract) – Extract with the primary extractor, escalating when it is weak.

**Attributes:**

- [**escalate_to**](#agrag-ingestion-extract-EscalatingExtractor-escalate_to) –
- [**max_concurrency**](#agrag-ingestion-extract-EscalatingExtractor-max_concurrency) –
- [**min_chunk_words**](#agrag-ingestion-extract-EscalatingExtractor-min_chunk_words) –
- [**min_confidence**](#agrag-ingestion-extract-EscalatingExtractor-min_confidence) –
- [**primary**](#agrag-ingestion-extract-EscalatingExtractor-primary) –

## `escalate_to` \{#agrag-ingestion-extract-EscalatingExtractor-escalate_to}

```python
escalate_to = escalate_to
```

## `extract` \{#agrag-ingestion-extract-EscalatingExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the primary extractor, escalating when it is weak.

**Parameters:**

- **chunk** (<code>[Chunk](../../common/data_models/chunk/Chunk-ref.md)</code>) – The chunk to read.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – The primary result, or the escalation result when escalation triggers.

## `max_concurrency` \{#agrag-ingestion-extract-EscalatingExtractor-max_concurrency}

```python
max_concurrency = min(primary.max_concurrency, escalate_to.max_concurrency)
```

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
