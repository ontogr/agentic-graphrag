---
title: agrag.retrieval.tracing
sidebar_label: tracing
---

# `agrag.retrieval.tracing` \{#agrag-retrieval-tracing}

Span helpers shared by the retrieval spans.

Every retrieval span that returns a list records the results the same way, so a
trace answers "what came back" without a second lookup.

**Functions:**

- [**filters_json**](filters_json.md) – Return the scope as JSON, an empty scope when `filters` is None.
- [**record_chunks**](record_chunks.md) – Record loaded chunks as OpenTelemetry-safe attributes.
- [**record_results**](record_results.md) – Write the results onto `span`.
- [**result_text**](result_text.md) – Return the text a result stands for.
- [**retrieval_span**](retrieval_span.md) – Open a `RETRIEVER` span that records the query and the scope.

**Attributes:**

- [**MAX_DOCUMENT_ATTRIBUTES**](MAX_DOCUMENT_ATTRIBUTES.md) –
