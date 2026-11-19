---
title: agrag.vectordb.qdrant.QdrantSettings
sidebar_label: QdrantSettings
---

# `agrag.vectordb.qdrant.QdrantSettings` \{#agrag-vectordb-qdrant-QdrantSettings}

Bases: <code>BaseSettings</code>

Qdrant connection and per-graph collection names.

**Attributes:**

- [**url**](#agrag-vectordb-qdrant-QdrantSettings-url) (<code>str</code>) – HTTP endpoint. Env: `QDRANT_URL`.
- [**api_key**](#agrag-vectordb-qdrant-QdrantSettings-api_key) (<code>SecretStr | None</code>) – Optional authentication secret. Env: `QDRANT_API_KEY`.
- [**require_tls**](#agrag-vectordb-qdrant-QdrantSettings-require_tls) (<code>bool</code>) – Require HTTPS for remote hosts without credentials too.
  Loopback is exempt. Env: `QDRANT_REQUIRE_TLS`.
- [**collection_prefix**](#agrag-vectordb-qdrant-QdrantSettings-collection_prefix) (<code>[CollectionPrefix](../settings/CollectionPrefix.md)</code>) – Required unique graph prefix, beginning with a letter.
  Env: `QDRANT_COLLECTION_PREFIX`.

## `api_key` \{#agrag-vectordb-qdrant-QdrantSettings-api_key}

```python
api_key: SecretStr | None = None
```

## `collection_prefix` \{#agrag-vectordb-qdrant-QdrantSettings-collection_prefix}

```python
collection_prefix: CollectionPrefix
```

## `model_config` \{#agrag-vectordb-qdrant-QdrantSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `require_tls` \{#agrag-vectordb-qdrant-QdrantSettings-require_tls}

```python
require_tls: bool = False
```

## `url` \{#agrag-vectordb-qdrant-QdrantSettings-url}

```python
url: str = 'http://localhost:6333'
```
