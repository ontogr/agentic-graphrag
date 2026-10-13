---
title: agrag.vectordb.errors.VectorStoreMissingExtraError
sidebar_label: VectorStoreMissingExtraError
---

# `agrag.vectordb.errors.VectorStoreMissingExtraError` \{#agrag-vectordb-errors-VectorStoreMissingExtraError}

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](VectorStoreError.md)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-vectordb-errors-VectorStoreMissingExtraError-extra) – The name of the package extra to install.

## `extra` \{#agrag-vectordb-errors-VectorStoreMissingExtraError-extra}

```python
extra = extra
```
