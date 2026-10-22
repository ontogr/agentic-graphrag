---
title: agrag.graphdb.settings.FalkorDBSettings
sidebar_label: FalkorDBSettings
---

# `agrag.graphdb.settings.FalkorDBSettings` \{#agrag-graphdb-settings-FalkorDBSettings}

Bases: <code>BaseSettings</code>

FalkorDB connection configuration.

**Attributes:**

- [**url**](#agrag-graphdb-settings-FalkorDBSettings-url) (<code>str</code>) – The Redis connection URL, including scheme (`rediss://` for
  TLS). Env: `FALKORDB_URL`.
- [**password**](#agrag-graphdb-settings-FalkorDBSettings-password) (<code>SecretStr | None</code>) – The Redis password, or None for a server without one.
  Env: `FALKORDB_PASSWORD`.
- [**graph**](#agrag-graphdb-settings-FalkorDBSettings-graph) (<code>str</code>) – The name of the graph (the Redis key) that holds all data.
  Env: `FALKORDB_GRAPH`.
- [**max_connections**](#agrag-graphdb-settings-FalkorDBSettings-max_connections) (<code>int</code>) – The size of the connection pool. Env:
  `FALKORDB_MAX_CONNECTIONS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`redis://`) and points at a
  non-local host while `password` is set. Use `rediss://` for a
  remote instance.

## `graph` \{#agrag-graphdb-settings-FalkorDBSettings-graph}

```python
graph: str = 'agrag'
```

## `max_connections` \{#agrag-graphdb-settings-FalkorDBSettings-max_connections}

```python
max_connections: int = 16
```

## `model_config` \{#agrag-graphdb-settings-FalkorDBSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='FALKORDB_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `password` \{#agrag-graphdb-settings-FalkorDBSettings-password}

```python
password: SecretStr | None = None
```

## `url` \{#agrag-graphdb-settings-FalkorDBSettings-url}

```python
url: str = 'redis://localhost:6379'
```
