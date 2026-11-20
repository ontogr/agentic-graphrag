---
title: agrag.evidence.contract.SEARCH_THEMES
sidebar_label: SEARCH_THEMES
---

# `agrag.evidence.contract.SEARCH_THEMES` \{#agrag-evidence-contract-SEARCH_THEMES}

```python
SEARCH_THEMES = 'Find themes in the configured documents: clusters of related entities found by community detection, each with the passages that mention its member entities. A score orders themes and is not a confidence. Membership comes from the last community detection run; documents added after that run are absent, and hidden or out-of-scope passages are filtered out. Use this tool for broad questions that span many documents; use search_evidence for passages and entity_search when the question names a thing. Pass the evidence ids of the passages you use to fetch_evidence.'
```
