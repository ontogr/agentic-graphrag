---
title: agrag.loaders.corpus.types.ErrorPolicy
sidebar_label: ErrorPolicy
---

# `agrag.loaders.corpus.types.ErrorPolicy` \{#agrag-loaders-corpus-types-ErrorPolicy}

Bases: <code>StrEnum</code>

The action to take when one source in a batch fails.

The policy applies to each source separately. `RAISE` is the default of
`Graph.add`.

**Attributes:**

- [**QUARANTINE**](#agrag-loaders-corpus-types-ErrorPolicy-QUARANTINE) – Set the failing source aside and record it in `quarantined_items`.
- [**RAISE**](#agrag-loaders-corpus-types-ErrorPolicy-RAISE) – Stop the whole run and raise the first error.
- [**SKIP**](#agrag-loaders-corpus-types-ErrorPolicy-SKIP) – Drop the failing source and count it in `skipped`.

## `QUARANTINE` \{#agrag-loaders-corpus-types-ErrorPolicy-QUARANTINE}

```python
QUARANTINE = 'quarantine'
```

Set the failing source aside and record it in `quarantined_items`.

## `RAISE` \{#agrag-loaders-corpus-types-ErrorPolicy-RAISE}

```python
RAISE = 'raise'
```

Stop the whole run and raise the first error.

## `SKIP` \{#agrag-loaders-corpus-types-ErrorPolicy-SKIP}

```python
SKIP = 'skip'
```

Drop the failing source and count it in `skipped`.
