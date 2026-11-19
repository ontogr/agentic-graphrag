---
title: agrag.candidates.search.search_candidates
sidebar_label: search_candidates
---

# `agrag.candidates.search.search_candidates` \{#agrag-candidates-search-search_candidates}

```python
search_candidates(graph_store:GraphStore, query:str, *, kind:CandidateKind | None = None, limit:int = 10) -> list[CandidateRecord]
```

Find candidates whose label or text holds any word of the query.

Search is lexical because candidates have no embedding. Rejected
candidates are excluded, and words shorter than three characters are
ignored.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The store that holds the candidates.
- **query** (<code>str</code>) – The words to look for.
- **kind** (<code>[CandidateKind](../../common/data_models/candidate/CandidateKind.md) | None</code>) – Only this kind. None searches every kind.
- **limit** (<code>int</code>) – The most candidates to return.

**Returns:**

- <code>list\[[CandidateRecord](../../common/data_models/candidate/CandidateRecord.md)\]</code> – Candidates ranked by matching-word count, then frequency.
