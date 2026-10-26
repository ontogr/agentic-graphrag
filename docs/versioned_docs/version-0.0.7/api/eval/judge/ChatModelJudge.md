---
title: agrag.eval.judge.ChatModelJudge
sidebar_label: ChatModelJudge
---

# `agrag.eval.judge.ChatModelJudge` \{#agrag-eval-judge-ChatModelJudge}

```python
ChatModelJudge(chat_model:Any, name:str, *, tracer:Tracer | None = None) -> None
```

Bases: <code>DeepEvalBaseLLM</code>

Wrap a LangChain chat model as a DeepEval judge.

Pass an instance as `model=` to any DeepEval metric. With a `schema`,
`generate` returns an instance of it. Without one, it returns the reply
text. Provider errors surface unchanged.

**Functions:**

- [**a_generate**](#agrag-eval-judge-ChatModelJudge-a_generate) – Run one judge call asynchronously. See `generate`.
- [**from_settings**](#agrag-eval-judge-ChatModelJudge-from_settings) – Build a judge from settings.
- [**generate**](#agrag-eval-judge-ChatModelJudge-generate) – Run one judge call, returning a `schema` instance or the reply text.
- [**get_model_name**](#agrag-eval-judge-ChatModelJudge-get_model_name) – Return the judge's model id.
- [**load_model**](#agrag-eval-judge-ChatModelJudge-load_model) – Return the wrapped chat model.

## `a_generate` \{#agrag-eval-judge-ChatModelJudge-a_generate}

```python
a_generate(prompt:str, schema:type[BaseModel] | None = None) -> Any
```

Run one judge call asynchronously. See `generate`.

## `from_settings` \{#agrag-eval-judge-ChatModelJudge-from_settings}

```python
from_settings(settings:EvalJudgeSettings, *, tracer:Tracer | None = None) -> ChatModelJudge
```

Build a judge from settings.

The chat model is copied with `settings.temperature` set. When that
is `None`, no temperature is set. A model that rejects the
parameter then needs `EVAL_JUDGE_TEMPERATURE` empty.

**Parameters:**

- **settings** (<code>[EvalJudgeSettings](../settings/EvalJudgeSettings.md)</code>) – The judge client config and temperature.
- **tracer** (<code>Tracer | None</code>) – Receives OpenInference spans for every judge call.
  None emits no spans.

## `generate` \{#agrag-eval-judge-ChatModelJudge-generate}

```python
generate(prompt:str, schema:type[BaseModel] | None = None) -> Any
```

Run one judge call, returning a `schema` instance or the reply text.

## `get_model_name` \{#agrag-eval-judge-ChatModelJudge-get_model_name}

```python
get_model_name() -> str
```

Return the judge's model id.

## `load_model` \{#agrag-eval-judge-ChatModelJudge-load_model}

```python
load_model() -> Any
```

Return the wrapped chat model.
