---
title: agrag.loaders.corpus.types.LoadStats
sidebar_label: LoadStats
---

# `agrag.loaders.corpus.types.LoadStats` \{#agrag-loaders-corpus-types-LoadStats}

```python
LoadStats(documents:int = 0, sources:int = 0, bytes_read:int = 0, skipped:int = 0, quarantined:int = 0, quarantined_items:list[StageFailure] = list()) -> None
```

Running tally of a corpus walk.

**Attributes:**

- [**documents**](#agrag-loaders-corpus-types-LoadStats-documents) (<code>int</code>) – The number of documents read so far.
- [**sources**](#agrag-loaders-corpus-types-LoadStats-sources) (<code>int</code>) – The number of sources read so far.
- [**bytes_read**](#agrag-loaders-corpus-types-LoadStats-bytes_read) (<code>int</code>) – The number of bytes read so far.
- [**skipped**](#agrag-loaders-corpus-types-LoadStats-skipped) (<code>int</code>) – The number of sources skipped so far.
- [**quarantined**](#agrag-loaders-corpus-types-LoadStats-quarantined) (<code>int</code>) – The number of sources quarantined so far.
- [**quarantined_items**](#agrag-loaders-corpus-types-LoadStats-quarantined_items) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – One StageFailure per quarantined source so far.

## `bytes_read` \{#agrag-loaders-corpus-types-LoadStats-bytes_read}

```python
bytes_read: int = 0
```

## `documents` \{#agrag-loaders-corpus-types-LoadStats-documents}

```python
documents: int = 0
```

## `quarantined` \{#agrag-loaders-corpus-types-LoadStats-quarantined}

```python
quarantined: int = 0
```

## `quarantined_items` \{#agrag-loaders-corpus-types-LoadStats-quarantined_items}

```python
quarantined_items: list[StageFailure] = field(default_factory=list)
```

## `skipped` \{#agrag-loaders-corpus-types-LoadStats-skipped}

```python
skipped: int = 0
```

## `sources` \{#agrag-loaders-corpus-types-LoadStats-sources}

```python
sources: int = 0
```
