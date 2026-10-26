---
title: agrag.common.data_models.index_record.SearchCall
sidebar_label: SearchCall
---

# `agrag.common.data_models.index_record.SearchCall` \{#agrag-common-data_models-index_record-SearchCall}

```python
SearchCall(text:str, params:dict[str, Any] = dict()) -> None
```

A Cypher fragment that searches one index, plus the parameters it needs.

The fragment starts with `CALL` and ends after `YIELD node, score`. It
expects `$k` (candidates to read) and either `$fulltext_terms` or
`$vector`. `score` is higher for a closer match whatever the backend's
own scale is.

**Attributes:**

- [**text**](#agrag-common-data_models-index_record-SearchCall-text) (<code>str</code>) – The Cypher fragment.
- [**params**](#agrag-common-data_models-index_record-SearchCall-params) (<code>dict\[str, Any\]</code>) – Parameters the fragment needs beyond the caller's own.

## `params` \{#agrag-common-data_models-index_record-SearchCall-params}

```python
params: dict[str, Any] = field(default_factory=dict)
```

## `text` \{#agrag-common-data_models-index_record-SearchCall-text}

```python
text: str
```
