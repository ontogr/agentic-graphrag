---
title: agrag.retrieval.errors.AllRetrievalMethodsFailedError
sidebar_label: AllRetrievalMethodsFailedError
---

# `agrag.retrieval.errors.AllRetrievalMethodsFailedError` \{#agrag-retrieval-errors-AllRetrievalMethodsFailedError}

```python
AllRetrievalMethodsFailedError(failures:dict[str, BaseException]) -> None
```

Bases: <code>[RetrievalError](RetrievalError.md)</code>

Every retrieval method a Recipe named failed.

Raised instead of returning an empty result list so a total
retrieval outage is not mistaken for a query with no matches.

**Attributes:**

- [**failures**](#agrag-retrieval-errors-AllRetrievalMethodsFailedError-failures) – Each failed method name mapped to the exception it
  raised.

## `failures` \{#agrag-retrieval-errors-AllRetrievalMethodsFailedError-failures}

```python
failures = failures
```
