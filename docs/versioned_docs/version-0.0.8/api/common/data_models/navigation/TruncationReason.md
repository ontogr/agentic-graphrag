---
title: agrag.common.data_models.navigation.TruncationReason
sidebar_label: TruncationReason
---

# `agrag.common.data_models.navigation.TruncationReason` \{#agrag-common-data_models-navigation-TruncationReason}

Bases: <code>StrEnum</code>

The bound that cut a navigation result.

**Attributes:**

- [**LIMIT**](#agrag-common-data_models-navigation-TruncationReason-LIMIT) – More items existed than the item limit allowed.
- [**CHARS**](#agrag-common-data_models-navigation-TruncationReason-CHARS) – The text budget ran out. The last item may be cut.

## `CHARS` \{#agrag-common-data_models-navigation-TruncationReason-CHARS}

```python
CHARS = 'chars'
```

## `LIMIT` \{#agrag-common-data_models-navigation-TruncationReason-LIMIT}

```python
LIMIT = 'limit'
```
