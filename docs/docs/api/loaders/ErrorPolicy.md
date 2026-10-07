---
title: agrag.loaders.ErrorPolicy
sidebar_label: ErrorPolicy
---

# `agrag.loaders.ErrorPolicy` \{#agrag-loaders-ErrorPolicy}

Bases: <code>StrEnum</code>

The action to take when one source in a batch fails.

The policy applies to each source separately. `RAISE` is the default of
`Graph.add`.

**Attributes:**

- [**QUARANTINE**](#agrag-loaders-ErrorPolicy-QUARANTINE) – Set the failing source aside and record it in `quarantined_items`.
- [**RAISE**](#agrag-loaders-ErrorPolicy-RAISE) – Stop the whole run and raise the first error.
- [**SKIP**](#agrag-loaders-ErrorPolicy-SKIP) – Drop the failing source and count it in `skipped`.

## `QUARANTINE` \{#agrag-loaders-ErrorPolicy-QUARANTINE}

```python
QUARANTINE = 'quarantine'
```

Set the failing source aside and record it in `quarantined_items`.

## `RAISE` \{#agrag-loaders-ErrorPolicy-RAISE}

```python
RAISE = 'raise'
```

Stop the whole run and raise the first error.

## `SKIP` \{#agrag-loaders-ErrorPolicy-SKIP}

```python
SKIP = 'skip'
```

Drop the failing source and count it in `skipped`.
