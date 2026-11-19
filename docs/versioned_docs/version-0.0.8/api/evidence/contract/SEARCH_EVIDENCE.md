---
title: agrag.evidence.contract.SEARCH_EVIDENCE
sidebar_label: SEARCH_EVIDENCE
---

# `agrag.evidence.contract.SEARCH_EVIDENCE` \{#agrag-evidence-contract-SEARCH_EVIDENCE}

```python
SEARCH_EVIDENCE = 'Search the configured documents for passages that match a query, by keyword, by meaning, or both. Each hit carries an evidence id and a snippet. A score orders hits and is not a confidence. No hits does not prove that the documents lack the information. Use this tool for passages. Use entity_search when the question names a thing, and search_themes for broad questions that span many documents. Pass the evidence ids of the hits you use to fetch_evidence before citing them.'
```
