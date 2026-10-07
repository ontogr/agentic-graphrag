---
title: agrag.ingestion.settings.CutoverJobSettings
sidebar_label: CutoverJobSettings
---

# `agrag.ingestion.settings.CutoverJobSettings` \{#agrag-ingestion-settings-CutoverJobSettings}

Bases: <code>BaseSettings</code>

Configuration for the Cutover Job crash-recovery machine.

**Attributes:**

- [**lease_ttl_seconds**](#agrag-ingestion-settings-CutoverJobSettings-lease_ttl_seconds) (<code>int</code>) – How long a worker lease stays valid before another
  worker can take it. Env: CUTOVER_JOB_LEASE_TTL_SECONDS.

Env prefix: `CUTOVER_JOB_`.

## `lease_ttl_seconds` \{#agrag-ingestion-settings-CutoverJobSettings-lease_ttl_seconds}

```python
lease_ttl_seconds: int = Field(default=60, gt=0)
```

## `model_config` \{#agrag-ingestion-settings-CutoverJobSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='CUTOVER_JOB_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```
