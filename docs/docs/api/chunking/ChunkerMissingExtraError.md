---
title: agrag.chunking.ChunkerMissingExtraError
sidebar_label: ChunkerMissingExtraError
---

# `agrag.chunking.ChunkerMissingExtraError` \{#agrag-chunking-ChunkerMissingExtraError}

```python
ChunkerMissingExtraError(strategy:str, extra:str) -> None
```

Bases: <code>[ChunkingError](base/ChunkingError.md)</code>

A chunker needs a package extra that is not installed.

**Attributes:**

- [**strategy**](#agrag-chunking-ChunkerMissingExtraError-strategy) – The strategy name that needs the extra.
- [**extra**](#agrag-chunking-ChunkerMissingExtraError-extra) – The package extra to install.

## `extra` \{#agrag-chunking-ChunkerMissingExtraError-extra}

```python
extra = extra
```

## `strategy` \{#agrag-chunking-ChunkerMissingExtraError-strategy}

```python
strategy = strategy
```
