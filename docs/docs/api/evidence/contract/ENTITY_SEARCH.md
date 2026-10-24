---
title: agrag.evidence.contract.ENTITY_SEARCH
sidebar_label: ENTITY_SEARCH
---

# `agrag.evidence.contract.ENTITY_SEARCH` \{#agrag-evidence-contract-ENTITY_SEARCH}

```python
ENTITY_SEARCH = "Find entities in the configured documents whose name or meaning matches a query, each with up to a few passages that mention it. A score orders hits and is not a confidence. An entity without passages is not stated by the current text. Use this tool when the question names a thing; use search_evidence for passages and search_themes for broad questions. Pass the evidence ids in a hit's support to fetch_evidence."
```
