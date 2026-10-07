---
title: agrag.eval.EvalJudgeSettings
sidebar_label: EvalJudgeSettings
---

# `agrag.eval.EvalJudgeSettings` \{#agrag-eval-EvalJudgeSettings}

Bases: <code>BaseSettings</code>

LLM client config for the eval judge.

**Attributes:**

- [**client**](#agrag-eval-EvalJudgeSettings-client) (<code>LLMClientConfig</code>) – The judge model's client config.
- [**temperature**](#agrag-eval-EvalJudgeSettings-temperature) (<code>Annotated\[float | None, NoDecode\]</code>) – The sampling temperature the judge sends. `None` sends
  none, for models that reject the parameter. Set
  `EVAL_JUDGE_TEMPERATURE` empty to get `None`.
  Env: `EVAL_JUDGE_TEMPERATURE`.

Env prefix: `EVAL_JUDGE_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-eval-EvalJudgeSettings-from_openai_compatible_env) – Build settings from OpenAI-compatible env vars.

## `client` \{#agrag-eval-EvalJudgeSettings-client}

```python
client: LLMClientConfig
```

## `from_openai_compatible_env` \{#agrag-eval-EvalJudgeSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> EvalJudgeSettings
```

Build settings from OpenAI-compatible env vars.

Loads `.env` first, then resolves `EVAL_JUDGE_BASE_URL`,
`EVAL_JUDGE_API_KEY` and `EVAL_JUDGE_MODEL_ID` through
pydantic-settings. Each falls back to the shared `LLM_*` variable
when unset or empty, so the judge is the agent's own model unless
`EVAL_JUDGE_*` is set. That model grades its own answers, which
biases scores upward. There is no default model.

**Returns:**

- <code>[EvalJudgeSettings](settings/EvalJudgeSettings.md)</code> – EvalJudgeSettings with one openai-generic client.

**Raises:**

- <code>ValueError</code> – No model id resolves from either set of variables.

## `model_config` \{#agrag-eval-EvalJudgeSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EVAL_JUDGE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `temperature` \{#agrag-eval-EvalJudgeSettings-temperature}

```python
temperature: Annotated[float | None, NoDecode] = 0.0
```
