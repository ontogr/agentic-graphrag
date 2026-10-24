---
title: agrag.evidence.citation.check_citations
sidebar_label: check_citations
---

# `agrag.evidence.citation.check_citations` \{#agrag-evidence-citation-check_citations}

```python
check_citations(evidence_ids:Sequence[str], fetched_ids:Iterable[str], *, scope:frozenset[str]) -> CitationResult
```

Return one verdict for each cited evidence id, in the order given.

A citation is `valid` when its document is in scope and it was fetched. A
span citation is also valid when its range lies inside a fetched span of the
same document and content hash. A wider range is `not_fetched`. A chunk
citation must equal a fetched id. A citation of a document outside the scope
is `unavailable`, even when the caller fetched it earlier. A string that
does not decode is `malformed`.

Pass only the ids whose fetch returned `ok`. An id from a `truncated` or
`partial` outcome names more text than the caller received.

**Parameters:**

- **evidence_ids** (<code>Sequence\[str\]</code>) – Evidence ids the answer cites.
- **fetched_ids** (<code>Iterable\[str\]</code>) – Evidence ids the caller fetched. A malformed entry is
  ignored.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents the caller may read.

**Returns:**

- <code>[CitationResult](../../common/data_models/evidence/CitationResult.md)</code> – One check for each cited id, in the same order.
