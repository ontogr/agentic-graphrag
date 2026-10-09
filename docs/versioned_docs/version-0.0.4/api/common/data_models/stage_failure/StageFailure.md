---
title: agrag.common.data_models.stage_failure.StageFailure
sidebar_label: StageFailure
---

# `agrag.common.data_models.stage_failure.StageFailure` \{#agrag-common-data_models-stage_failure-StageFailure}

Bases: <code>BaseModel</code>

One item's failure within a pipeline stage.

**Attributes:**

- [**item_id**](#agrag-common-data_models-stage_failure-StageFailure-item_id) (<code>str</code>) – The chunk id, mention id, or batch id — whichever unit
  the stage failed on.
- [**error_type**](#agrag-common-data_models-stage_failure-StageFailure-error_type) (<code>str</code>) – The exception's class name.
- [**error_message**](#agrag-common-data_models-stage_failure-StageFailure-error_message) (<code>str</code>) – The exception's message.
- [**trace_id**](#agrag-common-data_models-stage_failure-StageFailure-trace_id) (<code>str | None</code>) – The OTel trace id correlating to the full span detail,
  when tracing is configured.
- [**span_id**](#agrag-common-data_models-stage_failure-StageFailure-span_id) (<code>str | None</code>) – The OTel span id within that trace.

## `error_message` \{#agrag-common-data_models-stage_failure-StageFailure-error_message}

```python
error_message: str
```

## `error_type` \{#agrag-common-data_models-stage_failure-StageFailure-error_type}

```python
error_type: str
```

## `item_id` \{#agrag-common-data_models-stage_failure-StageFailure-item_id}

```python
item_id: str
```

## `span_id` \{#agrag-common-data_models-stage_failure-StageFailure-span_id}

```python
span_id: str | None = None
```

## `trace_id` \{#agrag-common-data_models-stage_failure-StageFailure-trace_id}

```python
trace_id: str | None = None
```
