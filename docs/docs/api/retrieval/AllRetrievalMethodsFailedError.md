---
title: agrag.retrieval.AllRetrievalMethodsFailedError
sidebar_label: AllRetrievalMethodsFailedError
---

# `agrag.retrieval.AllRetrievalMethodsFailedError` \{#agrag-retrieval-AllRetrievalMethodsFailedError}

```python
AllRetrievalMethodsFailedError(failures:dict[str, BaseException]) -> None
```

Bases: <code>[RetrievalError](errors/RetrievalError.md)</code>

Every retrieval method a Recipe named failed.

Raised instead of returning an empty result list so a total
retrieval outage is not mistaken for a query with no matches.

**Attributes:**

- [**failures**](#agrag-retrieval-AllRetrievalMethodsFailedError-failures) – Each failed method name mapped to the exception it
  raised.

## `failures` \{#agrag-retrieval-AllRetrievalMethodsFailedError-failures}

```python
failures = failures
```
