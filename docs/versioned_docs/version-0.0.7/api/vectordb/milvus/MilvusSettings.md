---
title: agrag.vectordb.milvus.MilvusSettings
sidebar_label: MilvusSettings
---

# `agrag.vectordb.milvus.MilvusSettings` \{#agrag-vectordb-milvus-MilvusSettings}

Bases: <code>BaseSettings</code>

Milvus or Zilliz Cloud connection and collection namespace.

**Attributes:**

- [**uri**](#agrag-vectordb-milvus-MilvusSettings-uri) (<code>str</code>) – HTTP(S) endpoint. Env: `MILVUS_URI`.
- [**token**](#agrag-vectordb-milvus-MilvusSettings-token) (<code>SecretStr | None</code>) – Optional authentication token. Env: `MILVUS_TOKEN`.
- [**collection_prefix**](#agrag-vectordb-milvus-MilvusSettings-collection_prefix) (<code>[CollectionPrefix](../settings/CollectionPrefix.md)</code>) – Required namespace unique to one graph, starting with
  a letter and containing at most 41 letters, digits or underscores.
  Env: `MILVUS_COLLECTION_PREFIX`.

Searches allow up to 16384 results. Zilliz gateways can impose an approximately
4 MB response cap; use smaller limits if that cap is reached. Milvus Lite and
embedded endpoints are unsupported.

## `collection_prefix` \{#agrag-vectordb-milvus-MilvusSettings-collection_prefix}

```python
collection_prefix: CollectionPrefix
```

## `model_config` \{#agrag-vectordb-milvus-MilvusSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `token` \{#agrag-vectordb-milvus-MilvusSettings-token}

```python
token: SecretStr | None = None
```

## `uri` \{#agrag-vectordb-milvus-MilvusSettings-uri}

```python
uri: str = 'http://localhost:19530'
```
