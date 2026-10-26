---
title: agrag.common.data_models.evidence.CitationVerdict
sidebar_label: CitationVerdict
---

# `agrag.common.data_models.evidence.CitationVerdict` \{#agrag-common-data_models-evidence-CitationVerdict}

Bases: <code>StrEnum</code>

Whether a citation traces to evidence the caller fetched.

**Attributes:**

- [**VALID**](#agrag-common-data_models-evidence-CitationVerdict-VALID) – The id decodes, is in scope, and was fetched, or lies inside a
  fetched span of the same version.
- [**NOT_FETCHED**](#agrag-common-data_models-evidence-CitationVerdict-NOT_FETCHED) – The id is in scope but was not fetched, or it reaches past
  every fetched span.
- [**UNAVAILABLE**](#agrag-common-data_models-evidence-CitationVerdict-UNAVAILABLE) – The id names a document outside the scope.
- [**MALFORMED**](#agrag-common-data_models-evidence-CitationVerdict-MALFORMED) – The id does not decode.

## `MALFORMED` \{#agrag-common-data_models-evidence-CitationVerdict-MALFORMED}

```python
MALFORMED = 'malformed'
```

## `NOT_FETCHED` \{#agrag-common-data_models-evidence-CitationVerdict-NOT_FETCHED}

```python
NOT_FETCHED = 'not_fetched'
```

## `UNAVAILABLE` \{#agrag-common-data_models-evidence-CitationVerdict-UNAVAILABLE}

```python
UNAVAILABLE = 'unavailable'
```

## `VALID` \{#agrag-common-data_models-evidence-CitationVerdict-VALID}

```python
VALID = 'valid'
```
