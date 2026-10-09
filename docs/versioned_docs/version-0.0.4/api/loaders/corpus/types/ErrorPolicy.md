---
title: agrag.loaders.corpus.types.ErrorPolicy
sidebar_label: ErrorPolicy
---

# `agrag.loaders.corpus.types.ErrorPolicy` \{#agrag-loaders-corpus-types-ErrorPolicy}

Bases: <code>StrEnum</code>

The action to take when one source in a batch fails.

RAISE: Stop the whole run with the first error.
SKIP: Drop the failing source and count it.
QUARANTINE: Set the failing source aside for review and count it.

**Attributes:**

- [**QUARANTINE**](#agrag-loaders-corpus-types-ErrorPolicy-QUARANTINE) –
- [**RAISE**](#agrag-loaders-corpus-types-ErrorPolicy-RAISE) –
- [**SKIP**](#agrag-loaders-corpus-types-ErrorPolicy-SKIP) –

## `QUARANTINE` \{#agrag-loaders-corpus-types-ErrorPolicy-QUARANTINE}

```python
QUARANTINE = 'quarantine'
```

## `RAISE` \{#agrag-loaders-corpus-types-ErrorPolicy-RAISE}

```python
RAISE = 'raise'
```

## `SKIP` \{#agrag-loaders-corpus-types-ErrorPolicy-SKIP}

```python
SKIP = 'skip'
```
