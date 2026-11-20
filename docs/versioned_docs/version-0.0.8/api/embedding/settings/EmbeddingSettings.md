---
title: agrag.embedding.settings.EmbeddingSettings
sidebar_label: EmbeddingSettings
---

# `agrag.embedding.settings.EmbeddingSettings` \{#agrag-embedding-settings-EmbeddingSettings}

Bases: <code>BaseSettings</code>

Configuration shared by the FastEmbed and sentence-transformers embedders.

All fields accept overrides through environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag-embedding-settings-EmbeddingSettings-model) (<code>str</code>) – The model name. The FastEmbed embedder takes a model that FastEmbed
  supports. The sentence-transformers embedder takes a model name or
  path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag-embedding-settings-EmbeddingSettings-device) (<code>str | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  Only the sentence-transformers embedder uses it, and `None` uses its
  own default detection. The FastEmbed embedder ignores it. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag-embedding-settings-EmbeddingSettings-normalize) (<code>bool</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag-embedding-settings-EmbeddingSettings-batch_size) (<code>int</code>) – The number of texts encoded per model call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag-embedding-settings-EmbeddingSettings-cache_folder) (<code>str | None</code>) – Where the model files are cached. `None` uses the library
  default. Env: `EMBEDDING_CACHE_FOLDER`.

## `batch_size` \{#agrag-embedding-settings-EmbeddingSettings-batch_size}

```python
batch_size: int = 32
```

## `cache_folder` \{#agrag-embedding-settings-EmbeddingSettings-cache_folder}

```python
cache_folder: str | None = None
```

## `device` \{#agrag-embedding-settings-EmbeddingSettings-device}

```python
device: str | None = None
```

## `model` \{#agrag-embedding-settings-EmbeddingSettings-model}

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

## `model_config` \{#agrag-embedding-settings-EmbeddingSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `normalize` \{#agrag-embedding-settings-EmbeddingSettings-normalize}

```python
normalize: bool = True
```
