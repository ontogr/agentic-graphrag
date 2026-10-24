---
title: agrag.evidence.rerank.CrossEncoderReranker
sidebar_label: CrossEncoderReranker
---

# `agrag.evidence.rerank.CrossEncoderReranker` \{#agrag-evidence-rerank-CrossEncoderReranker}

```python
CrossEncoderReranker(model:str) -> None
```

A reranker backed by a sentence-transformers CrossEncoder.

Requires the `embed-local` extra. The model loads lazily on the first
call, so constructing the reranker never downloads weights. Every
blocking call into the model runs in a worker thread so the event loop
stays free while a batch scores.

A running worker thread cannot be cancelled, so a caller timeout
(`asyncio.timeout` around the `await`) stops only the waiting, not
the prediction. Each call therefore runs its prediction inside a
semaphore and awaits it through `asyncio.shield`: a timed-out caller
gives up its wait while the prediction finishes, and the next call waits
on the semaphore instead of stacking a second prediction.

**Functions:**

- [**warm_up**](#agrag-evidence-rerank-CrossEncoderReranker-warm_up) – Load the model, so the first rerank call is not slow.

**Parameters:**

- **model** (<code>str</code>) – The sentence-transformers CrossEncoder model name/path.

**Raises:**

- <code>[EmbeddingMissingExtraError](../../embedding/errors/EmbeddingMissingExtraError.md)</code> – The `embed-local` extra is not installed.

## `warm_up` \{#agrag-evidence-rerank-CrossEncoderReranker-warm_up}

```python
warm_up() -> None
```

Load the model, so the first rerank call is not slow.
