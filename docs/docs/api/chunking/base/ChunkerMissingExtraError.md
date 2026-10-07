---
title: agrag.chunking.base.ChunkerMissingExtraError
sidebar_label: ChunkerMissingExtraError
---

# `agrag.chunking.base.ChunkerMissingExtraError` \{#agrag-chunking-base-ChunkerMissingExtraError}

```python
ChunkerMissingExtraError(strategy:str, extra:str) -> None
```

Bases: <code>[ChunkingError](ChunkingError.md)</code>

A chunker needs a package extra that is not installed.

**Attributes:**

- [**strategy**](#agrag-chunking-base-ChunkerMissingExtraError-strategy) – The strategy name that needs the extra.
- [**extra**](#agrag-chunking-base-ChunkerMissingExtraError-extra) – The package extra to install.

## `extra` \{#agrag-chunking-base-ChunkerMissingExtraError-extra}

```python
extra = extra
```

## `strategy` \{#agrag-chunking-base-ChunkerMissingExtraError-strategy}

```python
strategy = strategy
```
