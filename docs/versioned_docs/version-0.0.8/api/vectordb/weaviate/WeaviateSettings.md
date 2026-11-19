---
title: agrag.vectordb.weaviate.WeaviateSettings
sidebar_label: WeaviateSettings
---

# `agrag.vectordb.weaviate.WeaviateSettings` \{#agrag-vectordb-weaviate-WeaviateSettings}

Bases: <code>BaseSettings</code>

Weaviate connection and collection isolation settings.

**Attributes:**

- [**mode**](#agrag-vectordb-weaviate-WeaviateSettings-mode) (<code>Literal['cloud', 'custom']</code>) – Explicit cloud or custom deployment selection.
- [**url**](#agrag-vectordb-weaviate-WeaviateSettings-url) (<code>str</code>) – HTTP endpoint, including scheme and optional port.
- [**api_key**](#agrag-vectordb-weaviate-WeaviateSettings-api_key) (<code>SecretStr | None</code>) – Optional API key, hidden in representations and errors.
- [**grpc_port**](#agrag-vectordb-weaviate-WeaviateSettings-grpc_port) (<code>int</code>) – Custom deployment gRPC port. Cloud uses TLS on port 443.
- [**require_tls**](#agrag-vectordb-weaviate-WeaviateSettings-require_tls) (<code>bool</code>) – Require encryption for non-loopback custom deployments.
- [**collection_prefix**](#agrag-vectordb-weaviate-WeaviateSettings-collection_prefix) (<code>[CollectionPrefix](../settings/CollectionPrefix.md)</code>) – Required graph-specific prefix. Its first letter
  must be lowercase to prevent first-letter normalization collisions.

Environment variables use the `WEAVIATE_` prefix. Both HTTP and gRPC
must be reachable. Remote credentials require TLS on both transports.

## `api_key` \{#agrag-vectordb-weaviate-WeaviateSettings-api_key}

```python
api_key: SecretStr | None = None
```

## `collection_prefix` \{#agrag-vectordb-weaviate-WeaviateSettings-collection_prefix}

```python
collection_prefix: CollectionPrefix
```

## `grpc_port` \{#agrag-vectordb-weaviate-WeaviateSettings-grpc_port}

```python
grpc_port: int = Field(default=50051, ge=1, le=65535)
```

## `mode` \{#agrag-vectordb-weaviate-WeaviateSettings-mode}

```python
mode: Literal['cloud', 'custom'] = 'custom'
```

## `model_config` \{#agrag-vectordb-weaviate-WeaviateSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `require_tls` \{#agrag-vectordb-weaviate-WeaviateSettings-require_tls}

```python
require_tls: bool = False
```

## `url` \{#agrag-vectordb-weaviate-WeaviateSettings-url}

```python
url: str = 'http://localhost:8080'
```
