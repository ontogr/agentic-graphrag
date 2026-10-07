---
title: agrag.eval.VerdictItem
sidebar_label: VerdictItem
---

# `agrag.eval.VerdictItem` \{#agrag-eval-VerdictItem}

Bases: <code>BaseModel</code>

One fixed verifier input with its gold verdict.

**Attributes:**

- [**id**](#agrag-eval-VerdictItem-id) (<code>str</code>) – A stable id for the item.
- [**question**](#agrag-eval-VerdictItem-question) (<code>str</code>) – The original question.
- [**sub_questions**](#agrag-eval-VerdictItem-sub_questions) (<code>list\[str\]</code>) – The sub-questions the question was split into.
- [**findings**](#agrag-eval-VerdictItem-findings) (<code>str</code>) – The findings text with citation keys such as `E1`.
- [**gold**](#agrag-eval-VerdictItem-gold) (<code>Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']</code>) – The verdict the verifier should give.
- [**human_reviewed**](#agrag-eval-VerdictItem-human_reviewed) (<code>bool</code>) – True when a person confirmed the gold label.

## `findings` \{#agrag-eval-VerdictItem-findings}

```python
findings: str
```

## `gold` \{#agrag-eval-VerdictItem-gold}

```python
gold: Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']
```

## `human_reviewed` \{#agrag-eval-VerdictItem-human_reviewed}

```python
human_reviewed: bool = False
```

## `id` \{#agrag-eval-VerdictItem-id}

```python
id: str
```

## `question` \{#agrag-eval-VerdictItem-question}

```python
question: str
```

## `sub_questions` \{#agrag-eval-VerdictItem-sub_questions}

```python
sub_questions: list[str]
```
