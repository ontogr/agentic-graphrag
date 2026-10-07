---
title: agrag.eval.ExtractionGold
sidebar_label: ExtractionGold
---

# `agrag.eval.ExtractionGold` \{#agrag-eval-ExtractionGold}

Bases: <code>BaseModel</code>

One gold-annotated chunk of text.

**Attributes:**

- [**id**](#agrag-eval-ExtractionGold-id) (<code>str</code>) – A stable id for the item. It seeds the chunk and document ids.
- [**text**](#agrag-eval-ExtractionGold-text) (<code>str</code>) – The chunk text the extractor reads.
- [**gold**](#agrag-eval-ExtractionGold-gold) (<code>[ExtractionResult](../common/data_models/extraction/ExtractionResult.md)</code>) – The annotation. Entity offsets index into `text`.

## `gold` \{#agrag-eval-ExtractionGold-gold}

```python
gold: ExtractionResult
```

## `id` \{#agrag-eval-ExtractionGold-id}

```python
id: str
```

## `text` \{#agrag-eval-ExtractionGold-text}

```python
text: str
```
