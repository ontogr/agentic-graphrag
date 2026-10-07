---
title: agrag.graphdb.Neo4jSettings
sidebar_label: Neo4jSettings
---

# `agrag.graphdb.Neo4jSettings` \{#agrag-graphdb-Neo4jSettings}

Bases: <code>BaseSettings</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag-graphdb-Neo4jSettings-uri) (<code>str</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag-graphdb-Neo4jSettings-username) (<code>str</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag-graphdb-Neo4jSettings-password) (<code>SecretStr</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag-graphdb-Neo4jSettings-database) (<code>str</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag-graphdb-Neo4jSettings-max_connection_lifetime) (<code>int</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

**Raises:**

- <code>ValueError</code> – `uri` is plaintext (`bolt://` or `neo4j://`) and
  points at a non-local host. Neo4j always authenticates with a
  password, so a plaintext scheme always sends it in the clear; use
  `neo4j+s://` (or `bolt+s://`) for a remote instance.

## `database` \{#agrag-graphdb-Neo4jSettings-database}

```python
database: str = 'neo4j'
```

## `max_connection_lifetime` \{#agrag-graphdb-Neo4jSettings-max_connection_lifetime}

```python
max_connection_lifetime: int = 240
```

## `model_config` \{#agrag-graphdb-Neo4jSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `password` \{#agrag-graphdb-Neo4jSettings-password}

```python
password: SecretStr = SecretStr('neo4j')
```

## `uri` \{#agrag-graphdb-Neo4jSettings-uri}

```python
uri: str = 'bolt://localhost:7687'
```

## `username` \{#agrag-graphdb-Neo4jSettings-username}

```python
username: str = 'neo4j'
```
