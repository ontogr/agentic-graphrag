---
title: agrag.common.data_models.normalization.Normalization
sidebar_label: Normalization
---

# `agrag.common.data_models.normalization.Normalization` \{#agrag-common-data_models-normalization-Normalization}

Bases: <code>BaseModel</code>

How a loader turned source bytes into `Document.text`.

Provenance offsets index the normalized text. A caller who needs offsets into
the raw source chooses `Normalization(bom="keep", newline="keep", unicode_form="none")`.

**Attributes:**

- [**bom**](#agrag-common-data_models-normalization-Normalization-bom) (<code>Literal['strip', 'keep']</code>) – `"strip"` removes a leading byte-order mark. `"keep"` leaves it.
- [**newline**](#agrag-common-data_models-normalization-Normalization-newline) (<code>Literal['lf', 'keep']</code>) – `"lf"` turns CRLF and CR into LF. `"keep"` leaves them.
- [**unicode_form**](#agrag-common-data_models-normalization-Normalization-unicode_form) (<code>Literal['NFKC', 'NFC', 'NFD', 'NFKD', 'none']</code>) – The Unicode normalization form to apply, or `"none"`.

## `bom` \{#agrag-common-data_models-normalization-Normalization-bom}

```python
bom: Literal['strip', 'keep'] = 'strip'
```

## `model_config` \{#agrag-common-data_models-normalization-Normalization-model_config}

```python
model_config = ConfigDict(frozen=True, extra='forbid')
```

## `newline` \{#agrag-common-data_models-normalization-Normalization-newline}

```python
newline: Literal['lf', 'keep'] = 'lf'
```

## `unicode_form` \{#agrag-common-data_models-normalization-Normalization-unicode_form}

```python
unicode_form: Literal['NFKC', 'NFC', 'NFD', 'NFKD', 'none'] = 'NFKC'
```
