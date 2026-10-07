---
title: agrag.vectordb.settings.WeaviateSettings
sidebar_label: WeaviateSettings
---

# `agrag.vectordb.settings.WeaviateSettings` \{#agrag-vectordb-settings-WeaviateSettings}

Bases: <code>BaseSettings</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag-vectordb-settings-WeaviateSettings-mode) (<code>Literal['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag-vectordb-settings-WeaviateSettings-url) (<code>str</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag-vectordb-settings-WeaviateSettings-api_key) (<code>str</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag-vectordb-settings-WeaviateSettings-grpc_port) (<code>int</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.
- [**require_tls**](#agrag-vectordb-settings-WeaviateSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Weaviate on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `WEAVIATE_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Weaviate instance.

## `api_key` \{#agrag-vectordb-settings-WeaviateSettings-api_key}

```python
api_key: str = ''
```

## `grpc_port` \{#agrag-vectordb-settings-WeaviateSettings-grpc_port}

```python
grpc_port: int = 50051
```

## `mode` \{#agrag-vectordb-settings-WeaviateSettings-mode}

```python
mode: Literal['cloud', 'custom'] = 'custom'
```

## `model_config` \{#agrag-vectordb-settings-WeaviateSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `require_tls` \{#agrag-vectordb-settings-WeaviateSettings-require_tls}

```python
require_tls: bool = False
```

## `url` \{#agrag-vectordb-settings-WeaviateSettings-url}

```python
url: str = 'http://localhost:8080'
```
