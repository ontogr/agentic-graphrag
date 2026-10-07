---
title: agrag.vectordb.VectorStoreMissingExtraError
sidebar_label: VectorStoreMissingExtraError
---

# `agrag.vectordb.VectorStoreMissingExtraError` \{#agrag-vectordb-VectorStoreMissingExtraError}

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](errors/VectorStoreError.md)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-vectordb-VectorStoreMissingExtraError-extra) – The name of the package extra to install.

## `extra` \{#agrag-vectordb-VectorStoreMissingExtraError-extra}

```python
extra = extra
```
