---
title: agrag.ingestion.settings.ExtractionSettings
sidebar_label: ExtractionSettings
---

# `agrag.ingestion.settings.ExtractionSettings` \{#agrag-ingestion-settings-ExtractionSettings}

Bases: <code>BaseSettings</code>

Configuration for local entity and relation extraction.

Every score is between 0 and 1. `ExtractionLLMSettings` variables start
with `EXTRACTION_LLM_` and are not read here, so no field may start with
`llm_`.

The entity and relation thresholds, the relation floor, the entity band and
the candidate switch shape what `GlinerExtractor` keeps and reports.
Escalation controls are validated configuration only; they do not yet
affect extraction. `EscalatingExtractor` uses its own escalation
parameters.

**Attributes:**

- [**mode**](#agrag-ingestion-settings-ExtractionSettings-mode) (<code>Literal['gliner', 'hybrid', 'llm']</code>) – Extractor mode. `gliner` runs GLiNER only; `hybrid` runs
  GLiNER and may escalate weak chunks to the LLM; `llm` runs the
  LLM on every chunk. Escalation settings apply only to `hybrid`.
- [**model_name**](#agrag-ingestion-settings-ExtractionSettings-model_name) (<code>str</code>) – GLiNER checkpoint.
- [**dtype**](#agrag-ingestion-settings-ExtractionSettings-dtype) (<code>Literal['fp32', 'fp16', 'bf16']</code>) – Model precision: `fp32`, `fp16` or `bf16`.
- [**entity_threshold**](#agrag-ingestion-settings-ExtractionSettings-entity_threshold) (<code>\_Score</code>) – Minimum score for a kept entity span.
- [**relation_threshold**](#agrag-ingestion-settings-ExtractionSettings-relation_threshold) (<code>\_Score</code>) – Minimum score for a kept relation.
- [**relation_floor**](#agrag-ingestion-settings-ExtractionSettings-relation_floor) (<code>\_Score</code>) – Minimum relation score returned by the model.
- [**band_floor**](#agrag-ingestion-settings-ExtractionSettings-band_floor) (<code>\_Score</code>) – Minimum entity score in the band below the keep threshold.
- [**label_thresholds**](#agrag-ingestion-settings-ExtractionSettings-label_thresholds) (<code>dict\[str, \_Score\]</code>) – Per-label thresholds keyed by entity or relation label.
  An entity label's threshold replaces `entity_threshold` for that
  label. A relation label's threshold replaces `relation_threshold`
  as the cut for kept relations, and the model reads that relation at
  the lower of the threshold and `relation_floor`.
- [**escalation_threshold**](#agrag-ingestion-settings-ExtractionSettings-escalation_threshold) (<code>\_Score</code>) – Entity score below which a chunk may use the LLM.
- [**escalation_budget**](#agrag-ingestion-settings-ExtractionSettings-escalation_budget) (<code>\_Score | Literal['all']</code>) – LLM chunk share from 0 to 1, or `"all"` for no
  limit.
- [**min_escalation_words**](#agrag-ingestion-settings-ExtractionSettings-min_escalation_words) (<code>int</code>) – Minimum words for a chunk with no entities to
  use the LLM.
- [**candidates_enabled**](#agrag-ingestion-settings-ExtractionSettings-candidates_enabled) (<code>bool</code>) – Whether discarded items are kept as candidates.

Env prefix: `EXTRACTION_`. `label_thresholds` uses one JSON object,
such as `EXTRACTION_LABEL_THRESHOLDS='{"Person": 0.7}'`.

## `band_floor` \{#agrag-ingestion-settings-ExtractionSettings-band_floor}

```python
band_floor: _Score = 0.3
```

## `candidates_enabled` \{#agrag-ingestion-settings-ExtractionSettings-candidates_enabled}

```python
candidates_enabled: bool = True
```

## `dtype` \{#agrag-ingestion-settings-ExtractionSettings-dtype}

```python
dtype: Literal['fp32', 'fp16', 'bf16'] = 'fp32'
```

## `entity_threshold` \{#agrag-ingestion-settings-ExtractionSettings-entity_threshold}

```python
entity_threshold: _Score = 0.5
```

## `escalation_budget` \{#agrag-ingestion-settings-ExtractionSettings-escalation_budget}

```python
escalation_budget: _Score | Literal['all'] = 0.2
```

## `escalation_threshold` \{#agrag-ingestion-settings-ExtractionSettings-escalation_threshold}

```python
escalation_threshold: _Score = 0.75
```

## `label_thresholds` \{#agrag-ingestion-settings-ExtractionSettings-label_thresholds}

```python
label_thresholds: dict[str, _Score] = Field(default_factory=dict)
```

## `min_escalation_words` \{#agrag-ingestion-settings-ExtractionSettings-min_escalation_words}

```python
min_escalation_words: int = Field(default=8, ge=0)
```

## `mode` \{#agrag-ingestion-settings-ExtractionSettings-mode}

```python
mode: Literal['gliner', 'hybrid', 'llm'] = 'hybrid'
```

## `model_config` \{#agrag-ingestion-settings-ExtractionSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EXTRACTION_', env_file='.env', extra='ignore', hide_input_in_errors=True, protected_namespaces=())
```

## `model_name` \{#agrag-ingestion-settings-ExtractionSettings-model_name}

```python
model_name: str = 'fastino/gliner2.5-base-v1'
```

## `relation_floor` \{#agrag-ingestion-settings-ExtractionSettings-relation_floor}

```python
relation_floor: _Score = 0.3
```

## `relation_threshold` \{#agrag-ingestion-settings-ExtractionSettings-relation_threshold}

```python
relation_threshold: _Score = 0.7
```
