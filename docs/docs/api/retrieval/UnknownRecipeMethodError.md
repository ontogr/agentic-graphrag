---
title: agrag.retrieval.UnknownRecipeMethodError
sidebar_label: UnknownRecipeMethodError
---

# `agrag.retrieval.UnknownRecipeMethodError` \{#agrag-retrieval-UnknownRecipeMethodError}

```python
UnknownRecipeMethodError(unknown:list[str], known:list[str]) -> None
```

Bases: <code>[RetrievalError](errors/RetrievalError.md)</code>

A Recipe named a method SearchEngine does not know how to run.

A misspelled method name is a configuration error and must be
raised at search time so an empty successful search cannot
silently hide a typo.

**Attributes:**

- [**unknown**](#agrag-retrieval-UnknownRecipeMethodError-unknown) – The method names the recipe listed that are not in
  the retriever registry.
- [**known**](#agrag-retrieval-UnknownRecipeMethodError-known) – The method names this SearchEngine can run.

## `known` \{#agrag-retrieval-UnknownRecipeMethodError-known}

```python
known = list(known)
```

## `unknown` \{#agrag-retrieval-UnknownRecipeMethodError-unknown}

```python
unknown = list(unknown)
```
