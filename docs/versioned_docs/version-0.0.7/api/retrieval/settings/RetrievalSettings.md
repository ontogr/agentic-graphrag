---
title: agrag.retrieval.settings.RetrievalSettings
sidebar_label: RetrievalSettings
---

# `agrag.retrieval.settings.RetrievalSettings` \{#agrag-retrieval-settings-RetrievalSettings}

Bases: <code>BaseSettings</code>

Configuration for evidence search fusion and rerank.

**Attributes:**

- [**rrf_k**](#agrag-retrieval-settings-RetrievalSettings-rrf_k) (<code>int</code>) – The RRF constant controlling how much rank position
  matters.
- [**cross_encoder_model**](#agrag-retrieval-settings-RetrievalSettings-cross_encoder_model) (<code>str</code>) – The sentence-transformers CrossEncoder model
  used for hybrid rerank. Env:
  RETRIEVAL_CROSS_ENCODER_MODEL.
- [**rerank_enabled**](#agrag-retrieval-settings-RetrievalSettings-rerank_enabled) (<code>bool</code>) – Whether hybrid search reorders its top hits with the
  cross-encoder. Env: `RETRIEVAL_RERANK_ENABLED`.
- [**rerank_candidates**](#agrag-retrieval-settings-RetrievalSettings-rerank_candidates) (<code>int</code>) – How many of the top fused hits the cross-encoder
  scores. Env: `RETRIEVAL_RERANK_CANDIDATES`.
- [**rerank_timeout_seconds**](#agrag-retrieval-settings-RetrievalSettings-rerank_timeout_seconds) (<code>float</code>) – The most seconds one rerank call may take. A
  timed-out rerank keeps the fused order. Env:
  `RETRIEVAL_RERANK_TIMEOUT_SECONDS`.
- [**hybrid_alpha**](#agrag-retrieval-settings-RetrievalSettings-hybrid_alpha) (<code>float</code>) – Dense weight for hybrid searches on an external vector
  store. Env: `RETRIEVAL_HYBRID_ALPHA`.

Env prefix: `RETRIEVAL_`.

## `cross_encoder_model` \{#agrag-retrieval-settings-RetrievalSettings-cross_encoder_model}

```python
cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
```

## `hybrid_alpha` \{#agrag-retrieval-settings-RetrievalSettings-hybrid_alpha}

```python
hybrid_alpha: float = Field(default=0.5, ge=0, le=1)
```

## `model_config` \{#agrag-retrieval-settings-RetrievalSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='RETRIEVAL_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `rerank_candidates` \{#agrag-retrieval-settings-RetrievalSettings-rerank_candidates}

```python
rerank_candidates: int = Field(default=30, ge=1)
```

## `rerank_enabled` \{#agrag-retrieval-settings-RetrievalSettings-rerank_enabled}

```python
rerank_enabled: bool = True
```

## `rerank_timeout_seconds` \{#agrag-retrieval-settings-RetrievalSettings-rerank_timeout_seconds}

```python
rerank_timeout_seconds: float = Field(default=5.0, gt=0)
```

## `rrf_k` \{#agrag-retrieval-settings-RetrievalSettings-rrf_k}

```python
rrf_k: int = 60
```
