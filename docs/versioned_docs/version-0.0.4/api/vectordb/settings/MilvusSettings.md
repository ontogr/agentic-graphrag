---
title: agrag.vectordb.settings.MilvusSettings
sidebar_label: MilvusSettings
---

# `agrag.vectordb.settings.MilvusSettings` \{#agrag-vectordb-settings-MilvusSettings}

Bases: <code>BaseSettings</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag-vectordb-settings-MilvusSettings-uri) (<code>str</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag-vectordb-settings-MilvusSettings-token) (<code>str</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.
- [**require_tls**](#agrag-vectordb-settings-MilvusSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `uri` to a
  non-local host even with no `token` configured. Off by default
  since many deployments run an unauthenticated Milvus on a
  private network and rely on network segmentation rather than
  transport encryption. Env: `MILVUS_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `uri` is plaintext (`http`), points at a non-local
  host, and either `token` is set or `require_tls` is
  `True`. Use `https` for a remote Milvus instance.

## `model_config` \{#agrag-vectordb-settings-MilvusSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `require_tls` \{#agrag-vectordb-settings-MilvusSettings-require_tls}

```python
require_tls: bool = False
```

## `token` \{#agrag-vectordb-settings-MilvusSettings-token}

```python
token: str = ''
```

## `uri` \{#agrag-vectordb-settings-MilvusSettings-uri}

```python
uri: str = 'http://localhost:19530'
```
