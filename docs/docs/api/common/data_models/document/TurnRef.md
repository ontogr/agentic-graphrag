---
title: agrag.common.data_models.document.TurnRef
sidebar_label: TurnRef
---

# `agrag.common.data_models.document.TurnRef` \{#agrag-common-data_models-document-TurnRef}

Bases: <code>BaseModel</code>

One speaker turn in a chat document.

**Attributes:**

- [**role**](#agrag-common-data_models-document-TurnRef-role) (<code>str</code>) – The speaker of the turn, for example `"user"`.
- [**turn_id**](#agrag-common-data_models-document-TurnRef-turn_id) (<code>str | None</code>) – The id of the message in the source, when it has one.
- [**char_start**](#agrag-common-data_models-document-TurnRef-char_start) (<code>int</code>) – The start character offset of the turn in the document text.
- [**char_end**](#agrag-common-data_models-document-TurnRef-char_end) (<code>int</code>) – The end character offset of the turn, exclusive.

## `char_end` \{#agrag-common-data_models-document-TurnRef-char_end}

```python
char_end: int
```

## `char_start` \{#agrag-common-data_models-document-TurnRef-char_start}

```python
char_start: int
```

## `role` \{#agrag-common-data_models-document-TurnRef-role}

```python
role: str = Field(min_length=1)
```

## `turn_id` \{#agrag-common-data_models-document-TurnRef-turn_id}

```python
turn_id: str | None = None
```
