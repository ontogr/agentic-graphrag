---
title: agrag.vectordb.QdrantSettings
sidebar_label: QdrantSettings
---

# `agrag.vectordb.QdrantSettings` \{#agrag-vectordb-QdrantSettings}

Bases: <code>BaseSettings</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag-vectordb-QdrantSettings-url) (<code>str</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag-vectordb-QdrantSettings-api_key) (<code>str</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.
- [**require_tls**](#agrag-vectordb-QdrantSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Qdrant on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `QDRANT_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Qdrant instance.

## `api_key` \{#agrag-vectordb-QdrantSettings-api_key}

```python
api_key: str = ''
```

## `model_config` \{#agrag-vectordb-QdrantSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `require_tls` \{#agrag-vectordb-QdrantSettings-require_tls}

```python
require_tls: bool = False
```

## `url` \{#agrag-vectordb-QdrantSettings-url}

```python
url: str = 'http://localhost:6333'
```
