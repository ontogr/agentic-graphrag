---
title: agrag.ingestion.ExtractionLLMSettings
sidebar_label: ExtractionLLMSettings
---

# `agrag.ingestion.ExtractionLLMSettings` \{#agrag-ingestion-ExtractionLLMSettings}

Bases: <code>BaseSettings</code>

Env-backed LLM client config for the extraction role.

**Attributes:**

- [**clients**](#agrag-ingestion-ExtractionLLMSettings-clients) (<code>list\[LLMClientConfig\]</code>) – The LLM client(s) to use. One element for a single provider;
  more than one composed per `strategy`.
- [**strategy**](#agrag-ingestion-ExtractionLLMSettings-strategy) (<code>Literal['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. Ignored with one client.
- [**retry**](#agrag-ingestion-ExtractionLLMSettings-retry) (<code>RetryConfig</code>) – Retry settings applied to the extraction LLM call.

Env prefix: `EXTRACTION_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-ingestion-ExtractionLLMSettings-from_openai_compatible_env) – Build settings from a generic OpenAI-compatible endpoint.

## `clients` \{#agrag-ingestion-ExtractionLLMSettings-clients}

```python
clients: list[LLMClientConfig]
```

## `from_openai_compatible_env` \{#agrag-ingestion-ExtractionLLMSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> ExtractionLLMSettings
```

Build settings from a generic OpenAI-compatible endpoint.

Reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` from the
environment or `.env`, so the model name is never hardcoded. Raises
`RuntimeError` when the required variables are not all set.

**Returns:**

- <code>[ExtractionLLMSettings](extract/ExtractionLLMSettings.md)</code> – Settings pointing at one `openai-generic` client.

## `model_config` \{#agrag-ingestion-ExtractionLLMSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EXTRACTION_LLM_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `retry` \{#agrag-ingestion-ExtractionLLMSettings-retry}

```python
retry: RetryConfig = Field(default_factory=RetryConfig)
```

## `strategy` \{#agrag-ingestion-ExtractionLLMSettings-strategy}

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```
