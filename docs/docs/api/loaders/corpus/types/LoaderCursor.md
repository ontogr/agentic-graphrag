---
title: agrag.loaders.corpus.types.LoaderCursor
sidebar_label: LoaderCursor
---

# `agrag.loaders.corpus.types.LoaderCursor` \{#agrag-loaders-corpus-types-LoaderCursor}

```python
LoaderCursor(uri:str | None = None, record_index:int | None = None) -> None
```

Resume point for a corpus walk.

Ordering is deterministic, so a cursor is replayable.

**Attributes:**

- [**uri**](#agrag-loaders-corpus-types-LoaderCursor-uri) (<code>str | None</code>) – The source to resume after. `None` means start at the beginning.
- [**record_index**](#agrag-loaders-corpus-types-LoaderCursor-record_index) (<code>int | None</code>) – The record to resume after within the source. `None` means the
  start.

## `record_index` \{#agrag-loaders-corpus-types-LoaderCursor-record_index}

```python
record_index: int | None = None
```

## `uri` \{#agrag-loaders-corpus-types-LoaderCursor-uri}

```python
uri: str | None = None
```
