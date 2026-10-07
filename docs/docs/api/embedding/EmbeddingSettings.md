---
title: agrag.embedding.EmbeddingSettings
sidebar_label: EmbeddingSettings
---

# `agrag.embedding.EmbeddingSettings` \{#agrag-embedding-EmbeddingSettings}

Bases: <code>BaseSettings</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag-embedding-EmbeddingSettings-model) (<code>str</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag-embedding-EmbeddingSettings-device) (<code>str | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag-embedding-EmbeddingSettings-normalize) (<code>bool</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag-embedding-EmbeddingSettings-batch_size) (<code>int</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag-embedding-EmbeddingSettings-cache_folder) (<code>str | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

## `batch_size` \{#agrag-embedding-EmbeddingSettings-batch_size}

```python
batch_size: int = 32
```

## `cache_folder` \{#agrag-embedding-EmbeddingSettings-cache_folder}

```python
cache_folder: str | None = None
```

## `device` \{#agrag-embedding-EmbeddingSettings-device}

```python
device: str | None = None
```

## `model` \{#agrag-embedding-EmbeddingSettings-model}

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

## `model_config` \{#agrag-embedding-EmbeddingSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `normalize` \{#agrag-embedding-EmbeddingSettings-normalize}

```python
normalize: bool = True
```
